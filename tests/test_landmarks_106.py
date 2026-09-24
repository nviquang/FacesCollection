"""Unit test cho landmarks_106.LandmarkSource — KHÔNG cần insightface.

Dùng SimpleNamespace giả mặt (landmark_3d_68 shape (68,3) đúng kiểu insightface,
landmark_2d_106 shape (106,2)), test regression cho fix BUG #5: khi chỉ có
68-landmark (không có 106), trán fallback KHÔNG được trùng nasion.
Chạy: uv run python -m unittest discover tests
"""
import types
import unittest

import numpy as np

from landmarks_106 import LandmarkSource

# --- Bố cục mặt giả theo ISO 68 (tọa độ x,y tùy ý, chỉ z≈0) ---
# bbox: x1=100, y1=60, x2=300, y2=300 → w=200, h=240.
# Lông mày trong (21, 22) đặt ở y=150 (nửa DƯỚI bbox); glabella 27 ngay trên ở
# y=140 — cùng "eye level" như task yêu cầu (lông mày giữa chiều cao, trán trên).
BBOX = (100.0, 60.0, 300.0, 300.0)
_ITEMS = [
    (17, 140.0, 140.0),  # outer brow (tựa)
    (21, 150.0, 150.0), (22, 186.0, 150.0),  # 2 điểm TRONG lông mày: cùng y=150
    (27, 140.0, 140.0),  # glabella, giữa 2 mày = nasion khi exact
    (30, 190.0, 190.0),  # nose (fallback) — dưới glabella
]

_ARR = np.full((68, 3), 1000.0, dtype=np.float64)  # z-lớn để giá trị default không-trong-box
for i, x, y in _ITEMS:
    _ARR[i] = (x, y, 0.0)  # code chỉ đọc [i][0] và [i][1]; z đặt 0 cho đúng "3D"


def make_face(**attrs):
    """Face giả: tất cả landmarks mặc định nằm ngoài bbox; ghi đè theo attrs."""
    arr68 = _ARR.copy()
    face = types.SimpleNamespace(
        bbox=BBOX,
        landmark_3d_68=arr68,
    )
    for k, v in attrs.items():
        setattr(face, k, v)
    return face


class TestFallback68(unittest.TestCase):
    def setUp(self):
        # calib không có file — LandmarkSource tự nạp calib_anchors.json, vắng thì {}.
        self.lm = LandmarkSource()

    # --- test 1: nasion và down KHÁC NHAU khi chỉ có 68 ---
    def test_forehead_differs_from_nasion_68_only(self):
        face = make_face()  # KHÔNG có landmark_2d_106
        nasion = self.lm.point(face, "nasion")
        down = self.lm.point(face, "down")
        self.assertIsNotNone(nasion)
        self.assertIsNotNone(down)
        self.assertNotEqual(down, nasion, "trán (down) fallback KHÔNG được trùng nasion")

    # --- test 2: down ở TRÊN (y nhỏ hơn) nasion khi mày nằm nửa dưới bbox ---
    def test_forehead_above_nasion(self):
        face = make_face()
        _, nay = self.lm.point(face, "nasion")
        _, fhy = self.lm.point(face, "down")
        self.assertLess(fhy, nay, "trán (down) phải nằm trên (y nhỏ hơn) nasion")

    # --- test 3: down gần đỉnh bbox (y gần y1, trên tâm bbox) ---
    def test_forehead_near_top_of_bbox(self):
        face = make_face()
        fh = self.lm.point(face, "down")
        x1, y1, x2, y2 = BBOX
        fh_y_share = (fh[1] - y1) / (y2 - y1)
        self.assertAlmostEqual(fh[0], (x1 + x2) / 2.0, places=6)  # giữa theo x
        self.assertLess(fh_y_share, 0.5, "trán (down) phải ở nửa trên bbox")
        self.assertLess(fh_y_share, 0.3, "trán (down) phải sát đỉnh bbox (trên lông mày)")

    # --- test 4: không có CẢ 68 lẫn 106 → None ---
    def test_no_landmarks_returns_none(self):
        face = types.SimpleNamespace(bbox=BBOX)  # không 68, không 106
        self.assertIsNone(self.lm.point(face, "nasion"))
        self.assertIsNone(self.lm.point(face, "down"))

    # --- test 5: có 106 → dùng 106 (fix không đụng đường 2D-106) ---
    def test_106_used_when_present(self):
        lm_106 = np.zeros((106, 2), dtype=np.float64)
        lm_106[72] = (200.0, 205.0)   # nasion 106 index=72
        lm_106[86] = (215.0, 195.0)   # up 106 index=86
        face = make_face(landmark_2d_106=lm_106)
        self.assertEqual(self.lm.point(face, "nasion"), (200.0, 205.0))
        self.assertEqual(self.lm.point(face, "up"), (215.0, 195.0))

    # --- các trường hợp bbox hỏng → down None (không trùng nasion) ---
    def test_forehead_none_when_bbox_malformed(self):
        # bbox "hỏng": x2<=x1 (ngược), y2<=y1 (ngược), không phải số (None/chuỗi).
        for bad in [(100, 60, 80, 300), (100, 60, 300, 50), None, ("x", "y", "z", "w")]:
            face = make_face(bbox=bad)
            self.assertIsNone(
                self.lm.point(face, "down"),
                f"bbox {bad} phải cho down=None (không được trả nasion)",
            )
            # nasion vẫn chạy bình thường từ 68.
            nasion = self.lm.point(face, "nasion")
            self.assertIsNotNone(nasion, f"bbox {bad}: nasion vẫn phải có từ 68")

    def test_forehead_none_when_bbox_missing(self):
        face = make_face()
        del face.bbox
        self.assertIsNone(self.lm.point(face, "down"))
        self.assertIsNotNone(self.lm.point(face, "nasion"))

    # --- nasion: midpoint(21,22) vẫn hoạt động khi gọi trực tiếp (fallback phòng thủ) ---
    def test_nasion_midpoint_pair_fallback(self):
        face = make_face()
        # pair (21,22) có y cùng 150, x 150 vs 186 → trung điểm (168.0, 150.0).
        self.assertEqual(self.lm._midpoint_68(face, "nasion"), (168.0, 150.0))
        # exact_idx 27 (glabella) — nhánh point() dùng khi có 68.
        self.assertEqual(self.lm.point(face, "nasion"), (140.0, 140.0))


if __name__ == "__main__":
    unittest.main()