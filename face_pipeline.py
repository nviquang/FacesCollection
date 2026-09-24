"""Pipeline khuôn mặt cho game FaceRPG: detect, chọn face lớn nhất, crop, lọc chất lượng.

Dùng insightface (RetinaFace detect, model buffalo_l).
Ưu tiên chạy detect trên GPU (NVIDIA CUDA) nếu sẵn sàng; nếu không auto-fallback CPU.
Vai trò trong game: mỗi frame cung cấp face lớn nhất + độ nét/đạt chuẩn để game
lái landmark vào tâm và chụp crop ảnh. Embedding chưa dùng trong game — bước lưu
embedding cho recognition sẽ làm sau.
"""
from typing import List, Optional

import cv2
import numpy as np

import config

try:
    import insightface
    from insightface.app import FaceAnalysis
except ImportError:
    insightface = None
    FaceAnalysis = None


def _resolve_providers() -> tuple:
    """Chọn provider onnxruntime: ưu tiên CUDA → fallback CPU.

    Trả về (providers_list, ctx_id) cho FaceAnalysis.prepare().
    ctx_id=0 khi dùng GPU, -1 khi CPU.
    """
    if not config.USE_GPU:
        return (["CPUExecutionProvider"], -1)
    try:
        import onnxruntime as ort

        available = [p for p in ort.get_available_providers() if "CUDAExecutionProvider" in p]
        if available:
            return ([("CUDAExecutionProvider", {}), "CPUExecutionProvider"], config.CUDA_DEVICE_ID)
        print("[gpu] Không thấy CUDAExecutionProvider trong onnxruntime — fallback CPU.")
    except ImportError:
        print("[gpu] Thiếu onnxruntime — fallback CPU.")
    return (["CPUExecutionProvider"], -1)


class FaceDetector:
    """Bọc insightface FaceAnalysis. Detect được nhiều face 1 khung → chọn face lớn nhất."""

    def __init__(self, model_name: str = "buffalo_l", detect_every: int = 0,
                 providers: Optional[list] = None, ctx_id: Optional[int] = None) -> None:
        if FaceAnalysis is None:
            raise RuntimeError(
                "Chưa cài insightface. Chạy: uv sync (deps trong pyproject.toml)."
            )
        self._detect_every = max(0, detect_every)
        self._count = 0
        self._last_faces: tuple = ()
        if providers is None or ctx_id is None:
            providers, ctx_id = _resolve_providers()
        self.providers = providers
        self.ctx_id = ctx_id
        self.app = FaceAnalysis(
            name=model_name,
            allowed_modules=config.PIPELINE_MODULES,
            providers=providers,
        )
        self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))

    def set_detect_every(self, detect_every: int) -> None:
        """Đổi nhịp detect khi đang chạy (vd: preview mượt ↔ batch bám sát)."""
        self._detect_every = max(0, detect_every)
        self._count = 0

    def detect(self, frame: np.ndarray) -> List["Face"]:
        """Detect các khuôn mặt trong frame. Trả về list (rỗng nếu không có).

        Khi detect_every > 0, chỉ chạy detect lại mỗi (detect_every+1) frame;
        các frame giữa trả lại kết quả cũ (bbox lệch < 1 frame, vô hại).
        """
        if self._detect_every:
            self._count += 1
            if self._count % (self._detect_every + 1) != 0:
                return list(self._last_faces)
        try:
            faces = list(self.app.get(frame))
        except Exception as e:
            print(f"[face] Lỗi detect: {e}")
            faces = []
        self._last_faces = tuple(faces)
        return list(self._last_faces)

    @staticmethod
    def pick_largest(faces: List["Face"]):
        """Chọn khuôn mặt lớn nhất (gần camera nhất) làm đối tượng theo dõi."""
        if not faces:
            return None
        return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def face_width(face) -> float:
    """Bề rộng bbox của face (px)."""
    return float(face.bbox[2] - face.bbox[0])


def crop_face(frame: np.ndarray, face, margin: float = config.CROP_MARGIN) -> np.ndarray:
    """Crop khuôn mặt theo bbox, mở rộng thêm margin vào mỗi cạnh (chặn ngoài khung)."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = face.bbox
    bw, bh = x2 - x1, y2 - y1
    pad_x, pad_y = int(bw * margin), int(bh * margin)
    x1 = max(0, int(x1 - pad_x))
    y1 = max(0, int(y1 - pad_y))
    x2 = min(w, int(x2 + pad_x))
    y2 = min(h, int(y2 + pad_y))
    return frame[y1:y2, x1:x2].copy()


def sharpness(frame: np.ndarray) -> float:
    """Độ nét của ảnh xám dùng variance Laplacian (càng cao càng nét)."""
    if frame.size == 0:
        return 0.0
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def quality_ok(face, frame: np.ndarray, blur_face: np.ndarray) -> bool:
    """Khuôn mặt đạt chuẩn: score đủ cao, đủ to, crop đủ nét."""
    if face is None:
        return False
    if float(face.det_score) < config.SCORE_THRESHOLD:
        return False
    if face_width(face) < config.MIN_FACE_SIZE:
        return False
    if sharpness(blur_face) < config.SHARPNESS_THRESHOLD:
        return False
    return True


def sanitize(s: str) -> str:
    """student_id an toàn làm tên thư mục."""
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in s).strip()