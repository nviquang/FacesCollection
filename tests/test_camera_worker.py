"""Unit test cho camera_worker: tên clip (microsecond) + lock của video writer.

Không mở webcam và không cần QApplication — chỉ test phần thuần (pure):
  - make_clip_name() có microsecond → 2 clip trong cùng giây không trùng tên.
  - _writer_lock được tạo từ __init__ và start_clip/stop_clip gọi tuần tự
    (không chạy run(), không mở camera) không deadlock.

Chạy: uv run python -m unittest discover tests
"""
import time
import unittest

from camera_worker import CaptureWorker, make_clip_name


class TestMakeClipName(unittest.TestCase):
    def test_has_microseconds_and_format(self):
        """Tên phải có dạng clip_<date>_<HMS>_<µs>.mp4 (6 chữ số microsecond)."""
        ts = time.mktime(time.strptime("2026-09-24 12:34:56", "%Y-%m-%d %H:%M:%S"))
        ts_frac = ts + 0.123456
        name = make_clip_name(ts_frac)
        self.assertTrue(name.startswith("clip_2026-09-24_12-34-56_"), name)
        self.assertTrue(name.endswith(".mp4"), name)
        self.assertRegex(name, r"_(\d{6})\.mp4$")

    def test_same_ts_same_name(self):
        """Cùng timestamp → cùng tên (deterministic)."""
        ts = time.mktime(time.strptime("2026-01-02 03:04:05", "%Y-%m-%d %H:%M:%S")) + 0.987654
        self.assertEqual(make_clip_name(ts), make_clip_name(ts))

    def test_different_ts_differ(self):
        """Hai ts cách nhau 0.25s trong cùng giây → tên khác nhau."""
        ts = time.mktime(time.strptime("2026-01-02 03:04:05", "%Y-%m-%d %H:%M:%S"))
        self.assertNotEqual(make_clip_name(ts + 0.25), make_clip_name(ts))


class TestWriterLock(unittest.TestCase):
    def test_lock_exists_before_start(self):
        """_writer_lock phải được tạo sẵn trong __init__ (worker chưa chạy)."""
        w = CaptureWorker()
        self.assertIsNotNone(w._writer_lock)

    def test_start_stop_sequential_no_camera_no_deadlock(self):
        """start_clip khi chưa mở camera → None (không tạo writer); stop_clip
        không làm gì. Gọi tuần tự không được deadlock (chỉ test phần lock,
        KHÔNG mở webcam — cap cố tình là None)."""
        w = CaptureWorker()
        self.assertIsNone(w.start_clip(__import__("pathlib").Path("clips")))
        w.stop_clip()
        self.assertIsNone(w.clip_path())
        w.stop()


if __name__ == "__main__":
    unittest.main()