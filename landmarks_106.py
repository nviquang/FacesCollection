"""Bang anchor landmark dung cho game FaceRPG.

Muc tieu: tra ve toa do (x, y) tren khung hinh webcam cho 5 moc tren mat
ta muon lai vao tam man hinh: nasion (giua 2 long may — diem bat dau),
va 5 huong xoay dau: center, up, down, left, right.

Nguon landmark:
  - face.landmark_2d_106 (106 diem, model 2d106det) -- chinh, doc index tu bang.
  - face.landmark_3d_68  (68 diem, model 1k3d68) -- fallback; index 68 chuan.

Index da calibrate thuc te:
  - nasion (chinh dien / start): 72
  - center (chinh dien): 72
  - up (nguoc len): 86
  - down (cui xuong): composite -- x lay tu 72, y lay tu 105
  - left (go may trai): 35
  - right (go may phai): 93
"""
from typing import Dict, Optional, Tuple

import numpy as np

import config

# --- Ten moc dung dong bo trong game (key) ---
NASE = "nasion"      # giua 2 long may (glabella / goc mui) -- diem bat dau
CENTER = "center"    # chinh dien (72)
UP = "up"            # nguoc len (86)
DOWN = "down"        # cui xuong (composite x<-105, y<-72)
LEFT = "left"        # go may trai (35)
RIGHT = "right"      # go may phai (93)

# Index da calibrate thuc te bang --debug-landmarks.
# Down la composite: x tu index 105, y tu index 72.
_DEFAULT_2D_106: Dict[str, int] = {
    NASE: 72,             # chinh dien / start point
    CENTER: 72,           # chinh dien
    UP: 86,               # nguoc len
    DOWN: 72,             # placeholder -- xu ly composite trong point()
    LEFT: 35,             # go may trai
    RIGHT: 93,            # go may phai
}

# Index ISO 68 (chuan, gan nhu moi bo 68-point deu dung):
#   chin (menton) = 8; nose tip = 30; glabella ~ giua 2 long may = 27;
#   giua 2 may trai-phai = midpoint(21, 22);
# LUU Y: KHONG co DOWN o day -- 68 khong co index nao an toan cho tran (27 la
# glabella, trung nasion); tran duoc TONG HOP tu bbox mat (_forehead_68_from_bbox).
_68_FALLBACK = {
    UP: 30,
    CENTER: 30,
    LEFT: 2,         # be xuong go may trai (xac xi)
    RIGHT: 14,       # be xuong go may phai (xac xi)
}

# Midpoint theo CAP index (danh cho nasion fallback): (idx_a, idx_b) -> trung diem.
_MIDPOINTS_68 = {
    NASE: (21, 22),       # giua 2 diem trong long may -> giua 2 may
}

# Ti le chieu cao bbox de dat diem tran tong hop (gan dinh dau, tren long may).
_FOREHEAD_SYNTH_F = 0.08

# --- Composite landmark cho DOWN: lay x tu 72, y tu 105 ---
_DOWN_X_IDX = 72
_DOWN_Y_IDX = 105


def _forehead_68_from_bbox(face) -> Optional[Tuple[float, float]]:
    """Tong hop diem tran (DOWN) tu bbox RetinaFace khi fallback 68."""
    bbox = getattr(face, "bbox", None)
    try:
        x1, y1, x2, y2 = (float(v) for v in bbox[:4])
    except (TypeError, ValueError):
        x1 = y1 = x2 = y2 = float("nan")
    if not (x2 > x1 and y2 > y1):
        return None
    x = (x1 + x2) / 2.0
    y = y1 + _FOREHEAD_SYNTH_F * (y2 - y1)
    return x, y


class LandmarkSource:
    """Boc viec doc toa do moc tu Face cua insightface, co calibrate + fallback."""

    def __init__(self, calib: Optional[Dict[str, int]] = None) -> None:
        if calib is None:
            calib = load_calib()
        self._idx106: Dict[str, int] = dict(_DEFAULT_2D_106)
        if calib:
            for k, v in calib.items():
                if k in self._idx106 or k in (UP, CENTER, DOWN, LEFT, RIGHT):
                    self._idx106[k] = int(v)

    # --- interface chinh ---
    def point(self, face, name: str) -> Optional[Tuple[float, float]]:
        """Toa do (x, y) cua moc `name` trong khung hinh goc, None neu thieu."""
        lm106 = np.asarray(getattr(face, "landmark_2d_106", None))
        if lm106 is not None and lm106.ndim == 2 and lm106.shape[0] >= 106:
            # Down = composite: x tu 72, y tu 105
            if name == DOWN:
                if _DOWN_X_IDX < lm106.shape[0] and _DOWN_Y_IDX < lm106.shape[0]:
                    return float(lm106[_DOWN_X_IDX][0]), float(lm106[_DOWN_Y_IDX][1]-20)
            idx = self._idx106.get(name)
            if idx is not None and 0 <= idx < lm106.shape[0]:
                return float(lm106[idx][0]), float(lm106[idx][1])

        # Nasion dac biet: uu tien glabella/index truc tiep, fallback midpoint mat.
        if name == NASE:
            pt = self._midpoint_68(face, NASE, exact_idx=27)
            if pt is not None:
                return pt
        lm68 = np.asarray(getattr(face, "landmark_3d_68", None))
        if lm68 is not None and lm68.ndim == 2 and lm68.shape[0] >= 68:
            if name == DOWN:
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
        """106 diem 2D (raw) de ve so khi --debug-landmarks."""
        lm106 = np.asarray(getattr(face, "landmark_2d_106", None))
        if lm106 is not None and lm106.ndim == 2:
            return lm106
        return None


def load_calib() -> Dict[str, int]:
    """Nap calib_anchors.json neu co."""
    try:
        import json
        with open(config.CALIB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: int(v) for k, v in data.items() if isinstance(v, (int, float))}
    except (OSError, ValueError, TypeError):
        return {}


def save_calib(mapping: Dict[str, int]) -> None:
    """Ghi calib_anchors.json (idempotent, tao file neu chua co)."""
    import json
    with open(config.CALIB_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
