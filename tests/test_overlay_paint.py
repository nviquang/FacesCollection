"""Regression test: overlay.VideoView vẽ được bằng PyQt6 strict-typing.

Lỗi gốc: các lệnh QPainter gọi với số float (từ phép chia trong _update_geo)
chui vào overload int-only của PyQt6 → TypeError:
    drawImage(self, r: QRectF, image: QImage): argument 1 has unexpected type 'float'
    drawImage(self, x: int, y: int, ...): argument 1 has unexpected type 'float'

PyQt6 (khác PyQt5) là binding strict-typing: KHÔNG auto-coerce float→int, và
không có overload drawEllipse(QPointF, float, float). Toàn bộ paintEvent phải
gọi qua overload QPointF/QRectF hợp lệ.

Test này trigger TRỌN VẸN paintEvent bằng view.grab() (render to pixmap, offscreen,
không cần webcam). Trước fix: nó crash ngay tại dòng drawImage đầu tiên của
paintEvent (chính xác lỗi gốc). Sau fix: chạy đầy đủ → pass.

Chạy: uv run python -m unittest discover tests
"""
import unittest

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

import config
from camera_worker import FramePacket
from overlay import VideoView


def make_packet(frame_w: int = 640, frame_h: int = 480):
    """FramePacket giả: frame RGB đơn sắc + 1 điểm mốc + bbox, đủ cho toàn bộ overlay."""
    rgb = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)  # đen — dễ render, không cần đẹp
    rgb[::2, ::2] = 120                                     # vài pixel xám để không hoàn toàn trống
    cx, cy = frame_w / 2.0, frame_h / 2.0
    points = {
        "nasion": (cx, cy),
        "nose": (cx, cy + 10.0),
        "chin": (cx, cy + 30.0),
        "forehead": (cx, cy - 30.0),
        "left_cheek": (cx - 20.0, cy),
        "right_cheek": (cx + 20.0, cy),
    }
    face = None
    bbox = (cx - 150.0, cy - 180.0, cx + 150.0, cy + 180.0)  # mặt to → gate rộng
    return FramePacket(frame_bgr=rgb, points=points, face=face,
                       face_ok=True, bbox=bbox)


class TestVideoViewPaint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Giữ reference QApplication trong class: nếu app bị GC giữa lúc tạo
        # widget và render sẽ thành "QWidget: Must construct a QApplication".
        cls._qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view = VideoView()
        self.view.resize(800, 600)  # kích thước thật → _update_geo sinh offset/scale float

    def test_paint_full_path_no_typeerror(self):
        """Toàn bộ đường vẽ (video, reticle, gate, crosshair, highlight, progress,
        countdown, celebration) không được ném TypeError float-strict của PyQt6."""
        import game_logic
        self.view.set_packet(make_packet())
        self.view.state = game_logic.COLLECT
        self.view.current_target = (config.ANGLES[0][0], config.ANGLES[0][1], config.ANGLES[0][2])
        self.view.captured = []

        # Trigger đầy đủ paintEvent (render offscreen, không cần hiển thị).
        pixmap = self.view.grab()
        self.assertIsInstance(pixmap, QPixmap)
        self.assertFalse(pixmap.isNull())

    def test_paint_with_celebration_no_typeerror(self):
        """Pha pháo hoa (_draw_celebration + particles) cũng vẽ được (đã bắt bằng
        drawEllipse(QRectF)). Để tránh volatile timer, đặt particle thủ công."""
        self.view.set_packet(make_packet())
        self.view._celebration = {"phase": "explode", "t": 0.0,
                                  "origin": (400.0, 300.0)}
        self.view._fx_t0 = 1.0
        self.view._particles = [{"x": 400.0, "y": 300.0, "vx": 0.0, "vy": 0.0,
                                 "life": 1.0, "decay": 0.5,
                                 "color": (255, 60, 60), "size": 3.0}]
        self.view._video_size = (640, 480)
        pixmap = self.view.grab()
        self.assertIsInstance(pixmap, QPixmap)
        self.assertFalse(pixmap.isNull())


if __name__ == "__main__":
    unittest.main()