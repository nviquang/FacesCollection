"""Overlay & video widget cho FaceRPG (rẽ nét pygame/qt-free cho logic).

VideoView: QWidget vẽ frame webcam (scale phủ widget, giữ tỉ lệ khung 5/6) +
overlay game: reticle tâm, vòng R_ALIGN, highlight target, tiến trình 5 góc,
đếm ngược 3-2-1, và pháo hoa (particle QPainter).

Các toạ độ "điểm mốc" packet ở hệ toạ độ FRAME webcam → VideoView lưu scale
(video→widget) để vẽ đúng lên widget; reticle luôn ở tâm WIDGET (khớp tâm frame
vì worker không crop/scale).
"""
import math
import random
from typing import Dict, List, Tuple

import numpy as np

from PyQt6.QtCore import QPointF, QRectF, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PyQt6.QtWidgets import QWidget

import config
from game_logic import (ALIGN_NASION, CELEBRATE, COLLECT, COUNTDOWN, IDLE)
from camera_worker import FramePacket


class VideoView(QWidget):
    """Khung hiển thị camera + vẽ overlay game."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 360)
        self._packet: FramePacket = None
        self._video_qimage: QImage = None        # frame đã đổi sang RGB
        self._video_size = (0, 0)                # (w, h) của frame
        self._offset = (0, 0)                    # (dx, dy) vẽ video trong widget
        self._scale = 1.0                        # frame→widget (đều 2 trục)

        # Trạng thái game (MainWindow nạp mỗi khi có event/frame).
        self.state = IDLE
        self.countdown_num = 0
        self.current_target = None               # (key, label, landmark_name)
        self.captured: List[str] = []
        self.angle_defs = list(config.ANGLES)

        # Particle (đơn vị toạ độ WIDGET).
        self._particles: List[dict] = []
        self._celebration = None                 # {"phase","t","origin(widget)"}
        self._fx_timer = QTimer(self)
        self._fx_timer.setInterval(30)
        self._fx_timer.timeout.connect(self._tick_fx)
        self._fx_t0 = 0.0

        self.debug_landmarks = False             # bật = vẽ số 106 điểm
        self._lm106 = None

    # ------------------------------------------------------------- #
    def set_packet(self, pk: FramePacket) -> None:
        self._packet = pk
        if pk is not None and pk.frame_bgr is not None:
            rgb = np.ascontiguousarray(pk.frame_bgr[:, :, ::-1])  # BGR->RGB, contiguous
            h, w = rgb.shape[:2]
            self._video_qimage = QImage(rgb.data, w, h, rgb.strides[0],
                                        QImage.Format.Format_RGB888).copy()
            self._video_size = (w, h)
            if self.debug_landmarks:
                self._lm106 = getattr(pk.face, "landmark_2d_106", None)
        self.update()

    def set_debug_landmarks(self, on: bool) -> None:
        self.debug_landmarks = on

    # ------------------------------------------------------------- #
    # mapping frame→widget
    def _update_geo(self) -> None:
        if not self._video_size or self._video_size[0] == 0:
            self._offset = (0, 0)
            self._scale = 1.0
            return
        fw, fh = self._video_size
        sx = self.width() / fw
        sy = self.height() / fh
        self._scale = min(sx, sy)  # giữ tỉ lệ
        nw, nh = fw * self._scale, fh * self._scale
        self._offset = ((self.width() - nw) / 2, (self.height() - nh) / 2)

    def _frame_to_widget(self, x: float, y: float) -> Tuple[float, float]:
        return (x * self._scale + self._offset[0], y * self._scale + self._offset[1])

    @property
    def _center(self) -> Tuple[float, float]:
        return (self.width() / 2, self.height() / 2)

    # ------------------------------------------------------------- #
    def paintEvent(self, _e) -> None:
        self._update_geo()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(20, 20, 24))
        if self._video_qimage is not None:
            dx, dy = self._offset
            # Vẽ video scale phủ widget (đúng thiết kế trong docstring) — trước đây
            # vẽ 1:1 nên video nhỏ/lệch và các chấm overlay (scale) lệch khỏi video.
            nw = self._video_size[0] * self._scale
            nh = self._video_size[1] * self._scale
            p.drawImage(QRectF(dx, dy, nw, nh), self._video_qimage)
            self._draw_reticle(p)
            if self._packet is not None:
                self._draw_target_highlight(p)
            if self.debug_landmarks and self._lm106 is not None:
                self._draw_debug(p)
            self._draw_countdown(p)
            self._draw_progress(p)
            self._draw_celebration(p)
        else:
            p.setPen(Qt.GlobalColor.white)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Đang mở webcam…")
        p.end()

    # --- reticle --- #
    def _draw_reticle(self, painter: QPainter) -> None:
        cx, cy = self._center
        reaching = self._target_reaching()
        r = config.R_ALIGN * self._scale

        # Outer glow ring khi đang reaching (vẽ trước để bị đè)
        if reaching:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 255, 120, 40))
            painter.drawEllipse(QRectF(cx - r * 1.6, cy - r * 1.6,
                                       r * 3.2, r * 3.2))
            painter.setBrush(QColor(0, 255, 120, 20))
            painter.drawEllipse(QRectF(cx - r * 2.2, cy - r * 2.2,
                                       r * 4.4, r * 4.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)

        # Vòng R_ALIGN chính
        color = QColor(0, 255, 120) if reaching else QColor(240, 70, 70)
        painter.setPen(QPen(color, 2))
        painter.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))

        # Elip "gate xoay" (nasion phải ở trong) — co giãn theo bbox mặt như
        # game_logic._gate_rxy: rx theo yaw, ry cho cúi/ngước. Chỉ vào lúc thu.
        if self.state == COLLECT and self._packet is not None and self._packet.bbox is not None:
            x1, y1, x2, y2 = self._packet.bbox
            bw, bh = (float(x2) - float(x1)), (float(y2) - float(y1))
            rxg = max(config.R_GATE, config.R_GATE_SCALE_X * bw) * self._scale
            ryg = max(config.R_GATE, config.R_GATE_SCALE_Y * bh) * self._scale
            painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
            painter.drawEllipse(QRectF(cx - rxg, cy - ryg, 2 * rxg, 2 * ryg))

        # Dấu cộng tâm - 4 đoạn ngắn với gap ở giữa
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
        gap = 5
        arm = 12
        painter.drawLine(QPointF(cx - arm - gap, cy), QPointF(cx - gap, cy))
        painter.drawLine(QPointF(cx + gap, cy), QPointF(cx + arm + gap, cy))
        painter.drawLine(QPointF(cx, cy - arm - gap), QPointF(cx, cy - gap))
        painter.drawLine(QPointF(cx, cy + gap), QPointF(cx, cy + arm + gap))
        # Chấm tâm nhỏ
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.drawEllipse(QRectF(cx - 2, cy - 2, 4, 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _target_reaching(self) -> bool:
        """Đang đúng target trong R_ALIGN (đổi màu reticle)."""
        if self._packet is None or not self._video_size or self.state != COLLECT:
            return False
        if self.current_target is None:
            return False
        _, _, lm_name = self.current_target
        pt = self._packet.points.get(lm_name)
        if pt is None:
            return False
        fx, fy = self._frame_to_widget(*pt)
        cx, cy = self._center
        return (fx - cx) ** 2 + (fy - cy) ** 2 <= (config.R_ALIGN * self._scale) ** 2

    # --- highlight target hiện tại --- #
    def _draw_target_highlight(self, painter: QPainter) -> None:
        if self.state not in (ALIGN_NASION, COUNTDOWN, COLLECT):
            return
        # điểm bám: nasion khi đang align; target landmark khi collect.
        if self.state == COLLECT and self.current_target is not None:
            lm_name = self.current_target[2]
        else:
            lm_name = "nasion"
        pt = self._packet.points.get(lm_name)
        if pt is None:
            return
        fx, fy = self._frame_to_widget(*pt)
        painter.setBrush(QColor(0, 255, 120, 200))
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
        painter.drawEllipse(QRectF(fx - 8, fy - 8, 16, 16))

    # --- đếm ngược --- #
    def _draw_countdown(self, painter: QPainter) -> None:
        if self.state != COUNTDOWN or self.countdown_num <= 0:
            return
        cx, cy = self._center
        num_str = str(self.countdown_num)

        # Shadow (vẽ trước, lệch xuống phải)
        f_shadow = QFont(painter.font())
        f_shadow.setPointSize(72)
        f_shadow.setBold(True)
        painter.setFont(f_shadow)
        painter.setPen(QColor(0, 0, 0, 150))
        painter.drawText(
            QRectF(cx - 78, cy - 58, 160, 120),
            Qt.AlignmentFlag.AlignCenter,
            num_str,
        )

        # Text chính - vàng sáng
        f = QFont(painter.font())
        f.setPointSize(72)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor(250, 204, 21))
        painter.drawText(
            QRectF(cx - 80, cy - 60, 160, 120),
            Qt.AlignmentFlag.AlignCenter,
            num_str,
        )

    # --- progress 5 góc (bottom video, pills căn giữa) --- #
    def _draw_progress(self, painter: QPainter) -> None:
        if not self.angle_defs:
            return

        # Kích thước pill
        pill_w = 72
        pill_h = 22
        pill_r = 11      # border-radius
        spacing = 8
        total_w = len(self.angle_defs) * pill_w + (len(self.angle_defs) - 1) * spacing
        start_x = (self.width() - total_w) / 2
        y = self.height() - pill_h - 12

        current_key = None
        if self.current_target is not None:
            current_key = self.current_target[0]

        painter.setFont(QFont(painter.font().family(), 8))
        fm = painter.fontMetrics()

        for i, (key, label, _) in enumerate(self.angle_defs):
            x = start_x + i * (pill_w + spacing)
            rect = QRectF(x, y, pill_w, pill_h)
            done = key in self.captured
            is_current = (key == current_key)

            if done:
                # Xanh lá
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(20, 83, 45, 200))
                painter.drawRoundedRect(rect, pill_r, pill_r)
                painter.setPen(QPen(QColor(34, 197, 94, 180), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect, pill_r, pill_r)
                painter.setPen(QColor(134, 239, 172))
            elif is_current:
                # Xanh dương - đang cần
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(30, 58, 95, 220))
                painter.drawRoundedRect(rect, pill_r, pill_r)
                painter.setPen(QPen(QColor(59, 130, 246, 200), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect, pill_r, pill_r)
                painter.setPen(QColor(147, 197, 253))
            else:
                # Mờ - chưa tới
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(20, 24, 36, 160))
                painter.drawRoundedRect(rect, pill_r, pill_r)
                painter.setPen(QPen(QColor(60, 68, 90, 150), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect, pill_r, pill_r)
                painter.setPen(QColor(75, 85, 110))

            # Label text căn giữa pill (truncate nếu dài)
            display = label if fm.horizontalAdvance(label) < pill_w - 8 else label[:5] + ".."
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, display)

    # --- pháo hoa / đốm đỏ --- #
    def trigger_celebration(self, origin_frame: Tuple[float, float]) -> None:
        """Gọi khi DONE: đốm đỏ tại điểm mũi (frame coords) → grow → nổ pháo hoa."""
        fx, fy = self._frame_to_widget(*origin_frame)
        self._celebration = {"phase": "grow", "t": 0.0, "origin": (fx, fy)}
        self._particles = []
        self._fx_t0 = 0.0
        self._fx_timer.start()

    def _tick_fx(self) -> None:
        self._fx_t0 += 0.03
        t = self._fx_t0
        cb = self._celebration
        if cb is not None:
            if cb["phase"] == "grow" and t < 0.5:
                pass  # vẫn lớn dần
            elif cb["phase"] == "grow":
                cb["phase"] = "explode"
                ox, oy = cb["origin"]
                for _ in range(160):
                    ang = random.uniform(0, 2 * math.pi)
                    sp = random.uniform(60, 300)     # px/s
                    col = random.choice([(255, 60, 60), (255, 190, 40), (255, 255, 90),
                                         (90, 255, 160), (120, 180, 255), (255, 120, 220)])
                    self._particles.append({
                        "x": ox, "y": oy,
                        "vx": math.cos(ang) * sp, "vy": math.sin(ang) * sp - 40,
                        "life": 1.0, "decay": 0.5,  # /s, alpha mờ dần
                        "color": col, "size": random.uniform(2, 5),
                    })
            if t > 1.8:
                self._celebration = None
                self._particles = []
                self._fx_timer.stop()
        dt = 0.03
        GRAV = 420.0  # px/s^2
        keep = []
        for part in self._particles:
            part["x"] += part["vx"] * dt
            part["y"] += part["vy"] * dt
            part["vy"] += GRAV * dt
            part["life"] -= part["decay"] * dt
            if part["life"] > 0:
                keep.append(part)
        self._particles = keep
        self.update()

    def _draw_celebration(self, painter: QPainter) -> None:
        cb = self._celebration
        if cb is None:
            return
        t = self._fx_t0
        if cb["phase"] == "grow":
            rad = 6 + t * 320
            cx, cy = cb["origin"]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 30, 30, 220))
            painter.drawEllipse(QRectF(cx - rad, cy - rad, 2 * rad, 2 * rad))
            painter.setBrush(QColor(255, 140, 60, 120))
            painter.drawEllipse(QRectF(cx - rad * 1.4, cy - rad * 1.4,
                                       2 * rad * 1.4, 2 * rad * 1.4))
        for part in self._particles:
            alpha = int(255 * part["life"])
            r, g, b = part["color"]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(r, g, b, alpha))
            painter.drawEllipse(QRectF(part["x"] - part["size"], part["y"] - part["size"],
                                       2 * part["size"], 2 * part["size"]))

    # --- debug --- #
    def _draw_debug(self, painter: QPainter) -> None:
        lm = self._lm106
        if lm is None:
            return
        painter.setFont(QFont(painter.font().family(), 7))
        for i in range(lm.shape[0]):
            x, y = lm[i][0], lm[i][1]
            wx, wy = self._frame_to_widget(float(x), float(y))
            painter.setPen(QPen(QColor(90, 220, 255), 1))
            painter.drawPoint(int(wx), int(wy))
            painter.setPen(QColor(255, 255, 255, 200))
            painter.drawText(int(wx) + 2, int(wy) - 2, str(i))