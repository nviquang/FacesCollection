# DataCollectionForLMS

Thu thập dữ liệu khuôn mặt sinh viên từ webcam, phục vụ nhận diện SV trong lớp (recognition). App **PyQt6** (FaceRPG): người dùng **xoay đầu** để đưa từng mốc trên mặt (giữa 2 lông mày, mũi, cằm, trán, gò má trái/phải) vào **tâm màn hình**; đủ **5 góc** thì tự chụp 1 ảnh/góc + ghi **1 clip**, lưu theo `student_id`. Thay thế CLI cũ `collect_faces.py` (đã xoá).

## Chức năng chính

| File | Vai trò |
|---|---|
| `main.py` | Entry app (arg: `--debug-landmarks`, `--map <tên> <index>`) |
| `main_window.py` | Cửa sổ PyQt6: video + panel nhập `student_id`, nút Start, lưu kết quả |
| `game_logic.py` | State machine thuần Python (IDLE → ALIGN → COUNTDOWN → COLLECT 5 góc → CELEBRATE), test được |
| `camera_worker.py` | QThread: webcam + detect + ghi clip |
| `face_pipeline.py` | Detect + chọn face lớn nhất + crop + lọc chất lượng |
| `landmarks_106.py` | Bảng anchor 106 landmark + fallback 68 + calibrate |
| `overlay.py` | VideoView: reticle, đếm ngược, pháo hoa |
| `config.py` | Webcam + GPU + hằng số game |

## Cấu trúc

```
pyproject.toml        # deps do uv quản lý (opencv, insightface, onnxruntime, pyqt6, numpy<2)
main.py               # entry app (thường chạy: --debug-landmarks / --map để calibrate)
main_window.py        # cửa sổ: video trái + panel phải (student_id, Start)
video_capture.py      # helper: mở webcam, tạo VideoWriter
face_pipeline.py      # detect + chọn face lớn nhất + crop + lọc chất lượng
camera_worker.py      # QThread: webcam + detect + ghi clip
game_logic.py         # state machine 5 góc (thuần Python, không Qt — test được)
landmarks_106.py      # bảng anchor 106 + fallback 68 + calibrate
overlay.py            # VideoView: reticle, đếm ngược, pháo hoa
config.py             # webcam + GPU + hằng số game
data/
└── faces/{sid}/      # raw/ (5 ảnh crop theo góc), clips/, meta.json
tests/                # unit test logic game (chạy không cần webcam)
```

## Cách chạy (dùng uv — venv ảo, tránh xung đột hệ thống)

```bash
# Một lần đầu: tạo .venv + cài deps
uv sync

# Chạy game thu 5 góc mặt (nhập student_id, xoay đầu đưa mốc vào tâm, tự chụp + ghi clip)
uv run python main.py

# Chạy unit test (không cần webcam)
uv run python -m unittest discover tests
```

**Calibrate landmark** (chỉ lần đầu — model `2d106det` không có tài liệu index chính thức):

```bash
# In số 106 landmark lên video để xác định index đúng
uv run python main.py --debug-landmarks

# Ghi đè index vào calib_anchors.json cho từng mốc lệch
uv run python main.py --map nose 51
uv run python main.py --map nasion 35
```

Lần đầu chạy, insightface tự download model `buffalo_l` (RetinaFace + ArcFace).

## Lưu ý

- Embedding **chưa lưu ra đĩa** — game hiện chỉ thu crop ảnh 5 góc + 1 clip cho mỗi SV; bước lưu embedding & recognition sẽ làm sau.
- Index landmark 106 có thể cần calibrate thủ công 1 lần vào `calib_anchors.json` (xem mục Calibrate phía trên).
- Chạy lệnh qua `uv` (không dùng pip hệ thống) để tránh xung đột thư viện.