"""State machine thuần Python cho game FaceRPG — KHÔNG phụ thuộc Qt, test được.

Luồng (xem plan):
  IDLE --Start--> ALIGN_NASION --giữ chuẩn N frame--> COUNTDOWN --xong--> COLLECT
  COLLECT: lần lượt 5 target (mũi, cằm, trán, gò má trái/phải). Với mỗi target,
     điều kiện chụp = target landmark trong R_ALIGN quanh tâm màn hình ĐỒNG THỜI
     nasion vẫn quanh tâm trong R_GATE (chứng minh XOAY ĐẦU, không dịch cả mặt),
     giữ liên tiếp STABLE_FRAMES_CAPTURE frame → chụp → target kế.
  đủ 5 --> CELEBRATE (pháo hoa) --> về IDLE.

Event (báo cho UI):
  ALIGNING        bắt đầu đợi đưa nasion vào tâm
  COUNTDOWN(n)    đếm ngược i
  NEED_TARGET(key)  đang cần target (key)
  CAPTURED(key)   vừa chụp được target đó (có crop ảnh trong payload)
  DONE            đủ 5 góc, kêu pháo hoa
  HOLD_FAIL(title)  từng giữ chuẩn/thu nhưng lệch giữa chừng -> reset, gợi ý
"""
import math
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import config


# --- các trạng thái ---
IDLE = "IDLE"
ALIGN_NASION = "ALIGN_NASION"
COUNTDOWN = "COUNTDOWN"
COLLECT = "COLLECT"
CELEBRATE = "CELEBRATE"


@dataclass
class GameEvent:
    kind: str
    info: object = None  # 1-arg: n step / target key / ảnh crop ...


# Payload cho mỗi frame gửi vào logic (giữ logic không biết tới insightface).
@dataclass
class FrameState:
    points: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    # {name: (x, y)}
    frame_bgr: object = None  # để UI lưu frame gốc cho overlay khi chụp
    face: Optional[object] = None           # Face insightface (chỉ để lấy crop trong worker, không dùng trong logic)
    bbox: Optional[Tuple[float, float, float, float]] = None  # (x1, y1, x2, y2) của face
    face_ok: bool = True  # bbox đủ to + đạt score (worker tính) — gate chất lượng ảnh chụp


class GameSession:
    def __init__(self, on_event: Callable[[GameEvent], None], *, r_align: float = None,
                 r_gate: float = None, r_gate_sx: float = None, r_gate_sy: float = None,
                 stable_align: int = None, stable_capture: int = None,
                 angles: List[Tuple[str, str, str]] = None,
                 countdown: float = None, collect_timeout_secs: float = 15.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.on_event = on_event or (lambda e: None)
        self.r_align = r_align if r_align is not None else config.R_ALIGN
        self.r_gate = r_gate if r_gate is not None else config.R_GATE
        self.r_gate_sx = r_gate_sx if r_gate_sx is not None else config.R_GATE_SCALE_X
        self.r_gate_sy = r_gate_sy if r_gate_sy is not None else config.R_GATE_SCALE_Y
        # Dùng `is not None` (không phải `or`) để caller cấu hình được
        # stable_capture=0 (chụp ngay) hoặc angles=[].
        self.stable_align = stable_align if stable_align is not None else config.STABLE_FRAMES_ALIGN
        self.stable_capture = stable_capture if stable_capture is not None else config.STABLE_FRAMES_CAPTURE
        self.angles = angles if angles is not None else config.ANGLES
        self.countdown_secs = countdown if countdown is not None else config.COUNTDOWN_SECS
        self.collect_timeout_secs = collect_timeout_secs
        self._clock = clock

        self.state = IDLE
        self.student_id = ""
        self.target_index = 0          # vị trí trong self.angles
        self._hold_align = 0           # số frame liên tiếp nasion chuẩn (ALIGN_NASION)
        self._hold_capture = 0         # số frame liên tiếp target+gates chuẩn (COLLECT)
        self._collect_entered_at: Optional[float] = None  # mốc thời gian vào COLLECT (timeout cứu hộ)
        self._countdown_start: Optional[float] = None
        self._last_count = 0
        self.captured: List[str] = []  # key các góc đã chụp
        self.last_crop = None
        self.cx, self.cy = 320.0, 240.0

    # ------------------------------------------------------------------ #
    def start(self, student_id: str) -> None:
        self.student_id = student_id
        self.state = ALIGN_NASION
        self.target_index = 0
        self.captured = []
        self._hold_align = 0
        self._hold_capture = 0
        self._collect_entered_at = None
        self._countdown_start = None
        self.last_crop = None
        self.on_event(GameEvent("ALIGNING"))

    def inject_frame(self, fs: FrameState) -> None:
        """Gọi mỗi frame trong khi active; fs.points là dict name->(x,y)."""
        if self.state in (IDLE, CELEBRATE):
            return
        if self.state == ALIGN_NASION:
            return self._step_align(fs)
        if self.state == COUNTDOWN:
            return self._step_countdown(fs)
        # COLLECT
        self._step_collect(fs)

    # ------------------------------------------------------------------ #
    def _step_align(self, fs: FrameState) -> None:
        p = fs.points
        nasion = p.get("nasion")
        if fs.face_ok and _ok(nasion, *self._center(), self.r_align):
            self._hold_align += 1
            if self._hold_align >= self.stable_align:
                self.state = COUNTDOWN
                self._countdown_start = self._clock()
                self._hold_align = 0
        else:
            if self._hold_align > 0:
                self.on_event(GameEvent("HOLD_FAIL", "Đưa giữa lông mày vào tâm rồi giữ yên — gần xong!"))
            self._hold_align = 0

    def _step_countdown(self, fs: FrameState) -> None:
        elapsed = self._clock() - (self._countdown_start or self._clock())
        remaining = max(0, math.ceil(self.countdown_secs - elapsed))
        # Fire event mỗi khi số đếm giảm.
        if remaining != getattr(self, "_last_count", 0):
            self._last_count = remaining
            if remaining > 0:
                self.on_event(GameEvent("COUNTDOWN", remaining))
        if elapsed >= self.countdown_secs:
            self.state = COLLECT
            self._hold_capture = 0
            self._collect_entered_at = self._clock()
            self._last_count = 0
            self._emit_target()

    def _step_collect(self, fs: FrameState) -> None:
        if self.target_index >= len(self.angles):
            return
        _, _, lm_name = self.angles[self.target_index]

        # Cứu hộ: không thỏa được target nào quá lâu (vd điểm mốc index sai trong
        # calibrate) → về ALIGN_NASION để chạy lại, không treo vĩnh viễn.
        # Chuyển thẳng đến góc CHƯA chụp (không bắt lại từ đầu nếu đã có 1 số góc).
        entered = self._collect_entered_at
        if (entered is not None
                and self._clock() - entered > self.collect_timeout_secs):
            self._hold_capture = 0
            self._collect_entered_at = None
            # Tìm target đầu tiên chưa chụp
            captured_keys = set(self.captured)
            self.target_index = next(
                (i for i, (k, _, _) in enumerate(self.angles) if k not in captured_keys),
                len(self.angles)
            )
            self.state = ALIGN_NASION
            self.on_event(GameEvent("HOLD_FAIL",
                                    "Không đọc được điểm mốc — hãy về vị trí chính diện để bắt đầu lại, hoặc kiểm tra calibrate."))
            return

        if lm_name not in fs.points:
            # Mất target (mặt khuất/nằm ngoài frame) = giữ bị đứt → reset hold.
            if self._hold_capture > 0:
                self.on_event(GameEvent("HOLD_FAIL",
                            "Mất khuôn mặt — quay lại đúng vị trí."))
            self._hold_capture = 0
            return
        p = fs.points
        target_ok = _ok(p.get(lm_name), *self._center(), self.r_align)
        # Gate xoay: nasion còn đủ GẦN tâm (trong elip đã co theo bbox mặt) để
        # chứng minh đang XOAY đầu — chứ không dịch cả mặt đi chỗ khác rồi
        # "gắn" landmark lên tâm.
        nasion_ok = _ok_ellipse(p.get("nasion"), self._center(), self._gate_rxy(fs))
        if fs.face_ok and target_ok and nasion_ok:
            self._hold_capture += 1
            if self._hold_capture >= self.stable_capture:
                key, _, _ = self.angles[self.target_index]
                self.captured.append(key)
                # Crop ảnh do worker thực hiện; event CAPTURED chỉ mang key.
                self.on_event(GameEvent("CAPTURED", key))
                self.target_index += 1
                self._hold_capture = 0
                if self.target_index >= len(self.angles):
                    self.state = CELEBRATE
                    self.on_event(GameEvent("DONE"))
                else:
                    self._emit_target()
        else:
            if self._hold_capture > 0:
                self.on_event(GameEvent("HOLD_FAIL",
                            "Mất góc — quay lại đúng target hoặc giữ yên hơn."))
            self._hold_capture = 0

    def _emit_target(self) -> None:
        _, label, lm = self.angles[self.target_index]
        self.on_event(GameEvent("NEED_TARGET", {"key": self.angles[self.target_index][0],
                                                "label": label, "landmark": lm}))

    def reset(self) -> None:
        self.state = IDLE
        self.student_id = ""
        self.captured = []
        self._hold_align = 0
        self._hold_capture = 0
        self._collect_entered_at = None
        self._countdown_start = None
        self._last_count = 0

    def current_target(self) -> Optional[Tuple[str, str, str]]:
        if self.state == COLLECT and self.target_index < len(self.angles):
            return self.angles[self.target_index]
        return None

    def _center(self) -> Tuple[float, float]:
        # Tâm frame webcam (gốc); overlay dùng đúng tâm màn hình nên khớp nhau.
        return self.cx, self.cy

    def _gate_rxy(self, fs: FrameState) -> Tuple[float, float]:
        """Bán kính (rx, ry) của elip gate xoay theo bbox mặt (co giãn theo pose).

        rx theo chiều ngang (yaw — gò má trái/phải), ry theo chiều dọc
        (cúi/ngước — trán/cằm), đều có floor bằng R_GATE khi thiếu bbox.
        """
        rx = ry = self.r_gate
        bbox = fs.bbox
        if bbox:
            x1, y1, x2, y2 = bbox
            if x2 > x1 and y2 > y1:
                bw, bh = x2 - x1, y2 - y1
                rx = max(rx, self.r_gate_sx * bw)
                ry = max(ry, self.r_gate_sy * bh)
        return rx, ry

    def set_center(self, x: float, y: float) -> None:
        self.cx, self.cy = float(x), float(y)


def _ok(p, cx, cy, radius) -> bool:
    if p is None:
        return False
    return (p[0] - cx) ** 2 + (p[1] - cy) ** 2 <= radius * radius


def _ok_ellipse(p, center, rxy) -> bool:
    """p nằm trong elip tâm center, bán kính (rx, ry) — bỏ trục có r=0."""
    if p is None:
        return False
    px, py = p
    cx, cy = center
    rx, ry = rxy
    ex = ((px - cx) / rx) ** 2 if rx > 0 else 0.0
    ey = ((py - cy) / ry) ** 2 if ry > 0 else 0.0
    return ex + ey <= 1.0