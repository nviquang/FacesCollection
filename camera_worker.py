"""QThread worker chạy vòng webcam + detect + ghi clip cho game FaceRPG.

Sở hữu riêng cv2.VideoCapture + FaceDetector; mỗi frame:
  read → detect (nhịp DETECT_SKIP) → pick_largest → nếu worker đang recording
  thì ghi frame vào clip_writer → emit frameReady(packet).

Packet mang frame BGR gốc, điểm mốc (name→(x,y)) của face lớn nhất, face object
(dùng để crop khi logic báo chụp). UI main thread nhận qua signal queued — không
bao giờ chạy inference trên main thread.

Đồng bộ: `_stop` là cờ đơn giản; `_recording`, `_clip_writer`, `_clip_path`
được bảo vệ bằng `_writer_lock` (thread-safe) — UI thread tạo/release writer
qua `start_clip`/`stop_clip`, còn worker thread ghi frame; lock giữ cho
`write()` và `release()` không bao giờ chạy chồng nhau (cv2.VideoWriter không
thread-safe). `start_clip` được UI gọi rồi mới emit lệnh để worker bắt đầu
(order đủ cho use-case của app).
"""
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
from PyQt6.QtCore import QThread, pyqtSignal

import config
from face_pipeline import FaceDetector
from landmarks_106 import LandmarkSource
from video_capture import make_writer, open_webcam

# Các mốc game cần (khớp landmarks_106 + game_logic).
POINT_NAMES = ("nasion", "nose", "chin", "forehead", "left_cheek", "right_cheek")


def make_clip_name(ts: Optional[float] = None) -> str:
    """Tên file clip: clip_<YYYY-mm-dd>_<HH-MM-SS>_<µs>.mp4.

    Có microsecond (µs) để 2 clip trong cùng 1 giây không trùng tên
    (cancel-and-restart nhanh từng làm mất clip trước). Truyền `ts` để
    kết quả xác định (dễ test)."""
    t = time.localtime(ts) if ts is not None else time.localtime()
    ms = (ts - int(ts)) if ts is not None else time.time() % 1.0
    return f"clip_{time.strftime('%Y-%m-%d_%H-%M-%S', t)}_{int(ms * 1_000_000):06d}.mp4"


@dataclass
class FramePacket:
    frame_bgr: object                       # numpy BGR
    points: Dict[str, Tuple[float, float]]  # name→(x, y)
    face: object = None
    face_ok: bool = False                   # bbox đủ to + đạt score → có thể chụp
    bbox: Optional[Tuple[float, float, float, float]] = None  # (x1, y1, x2, y2)


class CaptureWorker(QThread):
    frameReady = pyqtSignal(object)  # FramePacket
    error = pyqtSignal(str)

    def __init__(self, lm: Optional[LandmarkSource] = None, parent=None) -> None:
        super().__init__(parent)
        self._lm = lm or LandmarkSource()
        self._writer_lock = threading.Lock()  # bảo vệ _recording/_clip_writer/_clip_path
        self.cap: Optional[cv2.VideoCapture] = None
        self.detector: Optional[FaceDetector] = None
        self._recording = False
        self._clip_writer = None
        self._clip_path: Optional[Path] = None
        self._stop = False

    # ---------- API từ UI thread ----------
    def start_clip(self, out_clips: Path) -> Optional[Path]:
        """Bật ghi clip: tạo VideoWriter vào out_clips. Trả path hoặc None."""
        if self.cap is None:
            return None
        self._stop_clip()
        p = out_clips / make_clip_name()
        w = make_writer(p, self.cap)
        if w is None:
            return None
        with self._writer_lock:
            self._clip_writer = w
            self._clip_path = p
            self._recording = True
        return p

    def stop_clip(self) -> None:
        self._stop_clip()

    def stop(self) -> None:
        self._stop = True

    def clip_path(self) -> Optional[Path]:
        with self._writer_lock:
            return self._clip_path

    @staticmethod
    def save_crop_if_ok(frame_bgr, face, out_path: Path) -> bool:
        """Crop + kiểm tra nét + ghi ảnh nếu đạt chuẩn. Trả True nếu đã ghi."""
        from face_pipeline import crop_face, quality_ok
        if face is None or frame_bgr is None:
            return False
        crop = crop_face(frame_bgr, face)
        ok = quality_ok(face, frame_bgr, crop)
        if ok:
            import cv2
            cv2.imwrite(str(out_path), crop)
        return ok

    # ---------- vòng lặp thread ----------
    def run(self) -> None:
        self.cap = open_webcam(config.WEBCAM_INDEX, label="game")
        if self.cap is None:
            self.error.emit("Không mở được webcam. Kiểm tra camera/USB.")
            return
        try:
            self.detector = FaceDetector(detect_every=config.GAME_DETECT_SKIP)
            while not self._stop:
                ret, frame = self.cap.read()
                if not ret:
                    self.error.emit("Mất kết nối webcam.")
                    break

                # Cam trước (laptop) hiển thị ngược → lật mirror ngay từ đầu để
                # preview soi gương + mọi output (landmark, clip, crop ảnh) nhất quán.
                frame = cv2.flip(frame, 1)

                face = None
                points: Dict[str, Tuple[float, float]] = {}
                try:
                    faces = self.detector.detect(frame)
                    face = FaceDetector.pick_largest(faces)
                    if face is not None:
                        for name in POINT_NAMES:
                            pt = self._lm.point(face, name)
                            if pt is not None:
                                points[name] = (float(pt[0]), float(pt[1]))
                except Exception as e:  # giữ worker sống khi 1 frame lỗi
                    print(f"[worker] lỗi detect: {e}")

                # Đọc cờ + ghi frame trong cùng 1 critical section: write() không
                # bao giờ chồng với release() từ start_clip/stop_clip (UI thread).
                with self._writer_lock:
                    if self._recording and self._clip_writer is not None:
                        self._clip_writer.write(frame)

                face_ok = False
                bbox = None
                if face is not None and float(face.det_score) >= config.SCORE_THRESHOLD:
                    bw = float(face.bbox[2] - face.bbox[0])
                    face_ok = bw >= config.MIN_FACE_SIZE
                    bbox = (float(face.bbox[0]), float(face.bbox[1]),
                            float(face.bbox[2]), float(face.bbox[3]))

                self.frameReady.emit(FramePacket(
                    frame_bgr=frame, points=points, face=face, face_ok=face_ok,
                    bbox=bbox))
        finally:
            self._stop_clip()
            if self.cap is not None:
                self.cap.release()
                self.cap = None

    def _stop_clip(self) -> None:
        with self._writer_lock:
            writer = self._clip_writer
            self._clip_writer = None
            self._clip_path = None
            self._recording = False
        # Release ngoài lock: write()/release() không chồng nhau (writer đã
        # tháo khỏi vùng nhìn của run()), nhưng vẫn gọi được nếu UI bấm stop.
        if writer is not None:
            try:
                writer.release()
            except Exception as e:
                print(f"[worker] Lỗi release video writer: {e}")