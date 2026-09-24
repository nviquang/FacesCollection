"""Bảng anchor landmark dùng cho game FaceRPG.

Mục tiêu: trả về toạ độ (x, y) trên khung hình webcam cho 5 mốc trên mặt
ta muốn lái vào tâm màn hình: nasion (giữa 2 lông mày), mũi, cằm, trán,
gò má trái, gò má phải.

Nguồn landmark:
  - face.landmark_2d_106 (106 điểm, model 2d106det) — chính, đọc index từ bảng.
  - face.landmark_3d_68  (68 điểm, model 1k3d68) — fallback; index 68 chuẩn.
  - Trán khi fallback 68: tổng hợp từ bbox mặt (68 điểm KHÔNG có index trán dùng
    được — index hay dùng 27 là glabella, trùng nasion → xem _forehead_68_from_bbox).

Lưu ý: insightface 0.7.3 KHÔNG có tài liệu chính thức chỉ mục 106 điểm → index
trong bảng ANCHORS_2D_106 là index MẶC ĐỊNH (ước từ thứ tự dataset WFLW-106).
Nếu thực tế điểm sai, calibrate bằng `--debug-landmarks` (in số lên frame) rồi
chạy `--map <tên> <index>` để ghi đè vào file calib_anchors.json; nếu thiếu
anchor 2D thì fallback sang 3D-68.
"""
from typing import Dict, Optional, Tuple

import numpy as np

import config

# --- Tên mốc dùng đồng bộ trong game (key) ---
NASE = "nasion"      # giữa 2 lông mày (glabella / gốc mũi)
NOSE = "nose"        # đầu mũi
CHIN = "chin"        # cằm
FOREHEAD = "forehead"  # trán (giữa, cao)
LEFT_CHEEK = "left_cheek"   # gò má trái
RIGHT_CHEEK = "right_cheek" # gò má phải

# Index mặc định cho mô hình 2D-106 (ước theo WFLW-106).
# Calibrate lại bằng --map nếu thấy lệch.
_DEFAULT_2D_106: Dict[str, int] = {
    NASE: 35,             # glabella / gốc mũi (giữa 2 mày)
    NOSE: 51,             # đầu mũi
    CHIN: 8,              # cằm
    FOREHEAD: 18,         # trán giữa
    LEFT_CHEEK: 88,       # gò má trái
    RIGHT_CHEEK: 96,      # gò má phải
}

# Index ISO 68 (chuẩn, gần như mọi bộ 68-point đều dùng):
#   chin (menton) = 8; nose tip = 30; glabella ~ giữa 2 lông mày = 27;
#   giữa 2 mày trái-phải = midpoint(21, 22);
#   gò má 2D — dùng xấp xỉ cạnh: point gần mắt/bờ má.
# LƯU Ý: KHÔNG có FOREHEAD ở đây — 68 không có index nào an toàn cho trán (27 là
# glabella, trùng nasion); trán được TỔNG HỢP từ bbox mặt (_forehead_68_from_bbox).
_68_FALLBACK = {
    NOSE: 30,
    CHIN: 8,
    LEFT_CHEEK: 2,        # bờ xương gò má trái (xấp xỉ)
    RIGHT_CHEEK: 14,      # bờ xương gò má phải (xấp xỉ)
}

# Midpoint theo CẶP index (dành cho nasion fallback và các điểm suy từ vai trò
# đối xứng): (idx_a, idx_b) → trung điểm. Dùng 68 + cặp mắt 68 đã chuẩn.
_MIDPOINTS_68 = {
    NASE: (21, 22),       # giữa 2 điểm trong lông mày -> giữa 2 mày
}

# Tỉ lệ chiều cao bbox để đặt điểm trán tổng hợp (gần đỉnh đầu, trên lông mày).
_FOREHEAD_SYNTH_F = 0.08


def _forehead_68_from_bbox(face) -> Optional[Tuple[float, float]]:
    """Tổng hợp điểm trán từ bbox RetinaFace khi fallback 68 (68 KHÔNG có index
    trán dùng được — index 27 là glabella, trùng nasion).

    RetinaFace bbox chạm đỉnh đầu → đỉnh bbox nằm trên trán. Đặt điểm trán ở
    x = giữa bbox (trục đối xứng ngang), y = y1 + f*(y2-y1) với f≈0.08 (gần mép
    trên bbox, phía trên lông mày — nasion nằm GIỮA 2 lông mày nên luôn thấp hơn).

    QUY ƯỚC: nếu bbox thiếu/sai (không phải 4 số, x2<=x1 hoặc y2<=y1) → trả None
    (không trả nasion!). Cách này giữ gate xoay an toàn: khác biệt trán/nasion bị
    MẤT thì game bỏ qua target trán thay vì xem nó đã "trúng".
    """
    bbox = getattr(face, "bbox", None)
    try:
        x1, y1, x2, y2 = (float(v) for v in bbox[:4])
    except (TypeError, ValueError):
        # bbox thiếu/không phải 4 số — không biết đỉnh đầu ở đâu.
        x1 = y1 = x2 = y2 = float("nan")
    if not (x2 > x1 and y2 > y1):
        return None
    x = (x1 + x2) / 2.0
    y = y1 + _FOREHEAD_SYNTH_F * (y2 - y1)
    return x, y


class LandmarkSource:
    """Bọc việc đọc toạ độ mốc từ Face của insightface, có calibrate + fallback."""

    def __init__(self, calib: Optional[Dict[str, int]] = None) -> None:
        # calib: dict {tên mốc: index-106} nạp từ file (ưu tiên hơn bảng mặc định).
        # Nếu không truyền, tự nạp file calib_anchors.json (main.py / MainWindow không truyền).
        if calib is None:
            calib = load_calib()
        self._idx106: Dict[str, int] = dict(_DEFAULT_2D_106)
        if calib:
            for k, v in calib.items():
                if k in self._idx106 or k in (NOSE, CHIN, FOREHEAD, LEFT_CHEEK, RIGHT_CHEEK):
                    self._idx106[k] = int(v)

    # --- interface chính ---
    def point(self, face, name: str) -> Optional[Tuple[float, float]]:
        """Toạ độ (x, y) của mốc `name` trong khung hình gốc, None nếu thiếu."""
        lm106 = np.asarray(getattr(face, "landmark_2d_106", None))
        if lm106 is not None and lm106.ndim == 2 and lm106.shape[0] >= 106:
            idx = self._idx106.get(name)
            if idx is not None and 0 <= idx < lm106.shape[0]:
                return float(lm106[idx][0]), float(lm106[idx][1])

        # Nasion đặc biệt: ưu tiên glabella/index trực tiếp, fallback midpoint mắt.
        if name == NASE:
            pt = self._midpoint_68(face, NASE, exact_idx=27)
            if pt is not None:
                return pt
        lm68 = np.asarray(getattr(face, "landmark_3d_68", None))
        if lm68 is not None and lm68.ndim == 2 and lm68.shape[0] >= 68:
            # Trán: 68 không có index trán dùng được (27 là glabella = nasion) →
            # tổng hợp từ bbox mặt (đỉnh bbox nằm trên trán), KHÔNG trả nasion.
            if name == FOREHEAD:
                return _forehead_68_from_bbox(face)
            idx = _68_FALLBACK.get(name)
            if idx is not None:
                return float(lm68[idx][0]), float(lm68[idx][1])
            if name == NASE:
                return self._midpoint_68(face, NASE)
        return None

    def _midpoint_68(self, face, name: str, exact_idx: Optional[int] = None) -> Optional[Tuple[float, float]]:
        lm68 = np.asarray(getattr(face, "landmark_3d_68", None))
        if lm68 is None or lm68.ndim != 2 or lm68.shape[0] < 68:
            return None
        # Ưu tiên index trực tiếp (exact_idx) cho nasion.
        if exact_idx is not None and exact_idx < lm68.shape[0]:
            return float(lm68[exact_idx][0]), float(lm68[exact_idx][1])
        pair = _MIDPOINTS_68.get(name)
        if not pair:
            return None
        a, b = pair
        if a >= lm68.shape[0] or b >= lm68.shape[0]:
            return None
        return ((lm68[a][0] + lm68[b][0]) / 2.0, (lm68[a][1] + lm68[b][1]) / 2.0)

    def all_points(self, face) -> Optional[np.ndarray]:
        """106 điểm 2D (raw) để vẽ số khi --debug-landmarks."""
        lm106 = np.asarray(getattr(face, "landmark_2d_106", None))
        if lm106 is not None and lm106.ndim == 2:
            return lm106
        return None


def load_calib() -> Dict[str, int]:
    """Nạp calib_anchors.json nếu có."""
    try:
        import json
        with open(config.CALIB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: int(v) for k, v in data.items() if isinstance(v, (int, float))}
    except (OSError, ValueError, TypeError):
        return {}


def save_calib(mapping: Dict[str, int]) -> None:
    """Ghi calib_anchors.json (idempotent, tạo file nếu chưa có)."""
    import json
    with open(config.CALIB_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)