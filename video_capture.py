"""Helper dùng chung: mở webcam, tạo VideoWriter ghi clip khuôn mặt."""
from pathlib import Path
from typing import Optional

import cv2

from config import RECORD_FPS_FALLBACK


def open_webcam(index: int = 0, label: str = "webcam"):
    """Mở webcam máy tính bằng cv2.VideoCapture(index). Trả về VideoCapture hoặc None.

    - Vì webcam trả frame ở độ phân giải khác nhau tùy máy, để kích thước hợp lý:
      không set WIDTH/HEIGHT ở đây — dùng FPS của webcam khi ghi clip.
    """
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"[{label}] Không mở được webcam index={index}. Kiểm tra camera/USB.")
        cap.release()
        return None
    return cap


def make_writer(filepath: Path, cap: cv2.VideoCapture) -> Optional[cv2.VideoWriter]:
    """Tạo VideoWriter mp4 theo đúng fps/kích thước của camera."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = cap.get(cv2.CAP_PROP_FPS) or RECORD_FPS_FALLBACK
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(str(filepath), fourcc, fps, (w, h))
    if not writer.isOpened():
        print(f"[video] Không tạo được video file: {filepath}")
        return None
    return writer