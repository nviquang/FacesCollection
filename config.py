"""Cấu hình chung cho game FaceRPG — thu thập dữ liệu khuôn mặt sinh viên (PyQt6).

Webcam + GPU (insightface) + hằng số game (ngưỡng "đạt chuẩn", 5 góc thu).
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FACES_DIR = DATA_DIR / "faces"    # dữ liệu khuôn mặt theo student_id

# --- Webcam ---
# Chỉ số thiết bị camera cho cv2.VideoCapture (0 = webcam mặc định của máy).
WEBCAM_INDEX = 0

# --- GPU (insightface) ---
# Ưu tiên chạy model trên GPU (NVIDIA CUDA) nếu onnxruntime-gpu + CUDA sẵn sàng.
# Khi không có CUDA, tự động fallback CPU (có log cảnh báo rõ).
USE_GPU = True
CUDA_DEVICE_ID = 0


def ensure_dirs() -> None:
    """Tạo thư mục dữ liệu nếu chưa tồn tại."""
    FACES_DIR.mkdir(parents=True, exist_ok=True)


# --- Calibration landmark (game) ---
# Bảng anchor 106-điểm dùng cho game; index có thể cần calibrate thủ công 1 lần
# (model 106 không có tài liệu index chính thức). Xem landmarks_106.py.
CALIB_FILE = BASE_DIR / "calib_anchors.json"


# --- Detect khuôn mặt (game) ---
RECORD_FPS_FALLBACK = 25.0  # fps ghi clip nếu camera không báo
MIN_FACE_SIZE = 100         # bbox >= 100px mới coi là đủ to (webcam — SV đứng gần máy)
SCORE_THRESHOLD = 0.5       # det_score tối thiểu của khuôn mặt
SHARPNESS_THRESHOLD = 80.0  # variance Laplacian — độ nét tối thiểu của crop
CROP_MARGIN = 0.4           # tỉ lệ mở rộng bbox khi crop khuôn mặt
# Detect cách quãng frame (detect mỗi GAME_DETECT_SKIP+1 frame, frame giữa dùng lại
# bbox cũ). Game cần landmark TƯƠI mỗi frame để bám target mượt → detect mọi frame.
GAME_DETECT_SKIP = 0
# Detect + landmark: game cần landmark dày (106 điểm 2D để lái điểm mốc vào tâm màn hình)
# và landmark 3D (68 điểm) để fallback/calibrate + pose pitch/yaw/roll khi debug.
# Embedding chưa cần trong game — bước lưu embedding cho recognition làm sau.
PIPELINE_MODULES = ["detection", "landmark_2d_106", "landmark_3d_68"]

# --- Game: thu 5 góc mặt (FaceRPG) ---
# Vị trí 2D-106 của các mốc sẽ được lấy từ landmarks_106.py; các hằng dưới là
# ngưỡng "đạt chuẩn" để chụp 1 góc.
R_ALIGN = 34.0              # bán kính (px) để 1 điểm mốc coi là "đúng tâm"
# "Gate xoay": nasion (giữa 2 lông mày) phải nằm trong HÌNH ELIP quanh tâm màn
# hình trong lúc lái landmark vào tâm. Bán kính đàn hồi theo kích thước bbox mặt
# (người càng gần camera, mặt càng to, vòng càng rộng):
#   rx = max(R_GATE, R_GATE_SCALE_X * bbox_w)   # theo chiều ngang (xoay yaw — gò má)
#   ry = max(R_GATE, R_GATE_SCALE_Y * bbox_h)   # theo chiều dọc (cúi/ngước — trán/cằm)
# Lý do: khi "ngước lên" để đưa CẰM vào tâm, nasion lệch lên ~0.5 chiều cao mặt
# — với mặt to (300px) đó là ~150px, nên khóang tròn tuyệt đối nhỏ là KHÔNG lấy
# được cằm/trán. ry rộng để cho phép pose cúi/ngước; rx vừa để cản lướt cả mặt
# sang ngang (đánh bùa gò má) — lướt xa phải vượt rx mới trúng tâm.
R_GATE = 90.0               # bán kính NỀN (floor); khi không có bbox → vòng tròn này
R_GATE_SCALE_X = 0.55       # nhân với bề rộng bbox để lấy rx (thường đủ cho xoay yaw)
R_GATE_SCALE_Y = 0.95       # nhân với chiều cao bbox để lấy vy (cho phép cúi/ngước sâu)
STABLE_FRAMES_ALIGN = 10    # số frame liên tiếp giữ chuẩn nasion trước khi đếm ngược
STABLE_FRAMES_CAPTURE = 8   # số frame liên tiếp đúng target+gates trước khi chụp
COUNTDOWN_SECS = 3          # đếm ngược 3-2-1 trước khi vào chế độ thu
# Thứ tự 5 góc thu. key = tên file/attr, label tiếng Việt, landmark mục tiêu.
ANGLES = [
    ("nose",       "Mũi (mặt chính diện)", "nose"),
    ("chin",       "Cằm (ngước lên)",      "chin"),
    ("forehead",   "Trán (cúi xuống)",     "forehead"),
    ("left_cheek", "Gò má trái",           "left_cheek"),
    ("right_cheek","Gò má phải",           "right_cheek"),
]