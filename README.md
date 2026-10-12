# DataCollectionForLMS — FaceRPG

Thu thập dữ liệu khuôn mặt sinh viên phục vụ nhận diện trong lớp học (face recognition).  
App **PyQt6** biến quá trình thu thành một trò chơi nhỏ: người dùng **xoay đầu** để đưa từng
mốc khuôn mặt (mũi, cằm, trán, gò má trái/phải) vào **đúng tâm màn hình**. Đủ **5 góc**
→ app tự chụp 1 ảnh/góc + ghi **1 clip** toàn quá trình, lưu theo `student_id`.

> Thay thế hoàn toàn CLI cũ (`collect_faces.py` đã bị xoá).

---

## Yêu cầu hệ thống

| | |
|---|---|
| **OS** | Windows 10/11 x64 (đã kiểm tra Windows 11) |
| **Python** | 3.11 hoặc 3.12 |
| **GPU** | NVIDIA với CUDA 12.x + cuDNN 9.x *(tùy chọn — có thể fallback CPU)* |
| **Webcam** | Webcam máy tính (mặc định chỉ số `0`) |

---

## Cài đặt

Có **hai cách** cài đặt. Khuyến khích dùng **`uv`** (cách 1) vì quản lý môi trường tự động.

---

### Cách 1 — dùng `uv` *(khuyến khích)*

**`uv`** là tool quản lý Python + virtualenv nhanh, tự động xử lý conflict dependencies.

#### 1a. Cài `uv` (nếu chưa có)

```bash
winget install astral-sh.uv
```

Sau đó mở terminal mới để `uv` vào PATH.

#### 1b. Cài dependencies & tạo môi trường ảo

```bash
uv sync
```

Lần đầu sẽ:
- Tạo `.venv/` trong thư mục dự án
- Cài tất cả packages theo `uv.lock` (pinned, reproducible)
- **Tự xử lý** xung đột giữa `onnxruntime` (CPU) và `onnxruntime-gpu` — không cần can thiệp thủ công

#### 1c. Chạy app

```bash
uv run python main.py
```

---

### Cách 2 — dùng `pip` + `venv` thủ công

> ⚠️ **Lưu ý quan trọng về ONNX:** `insightface` có thể kéo theo `onnxruntime` (bản CPU).
> Nếu cài hai bản cùng lúc, GPU sẽ **không được dùng**. Làm theo đúng thứ tự bên dưới.

#### 2a. Tạo virtualenv

```bash
python -m venv .venv
.venv\Scripts\activate
```

#### 2b. Cài packages

```bash
pip install -r requirements.txt
```

#### 2c. Kiểm tra không cài nhầm bản ONNX

```bash
pip list | findstr onnx
```

Kết quả **đúng** (chỉ có GPU, không có CPU):

```
onnx                1.x.x
onnxruntime-gpu     1.30.x
```

Nếu thấy `onnxruntime` (không có `-gpu`) → xoá và cài lại:

```bash
pip uninstall onnxruntime onnxruntime-gpu -y
pip install onnxruntime-gpu>=1.30
```

#### 2d. Chạy app

```bash
.venv\Scripts\activate   # nếu chưa activate
python main.py
```

---

## Sử dụng

### Chạy game thu 5 góc mặt

```bash
# uv
uv run python main.py

# pip
python main.py
```

### Luồng chơi

1. Nhập `student_id` (vd `B23DCCN691`) ở panel phải, bấm **Bắt đầu thu thập**.
2. Nhìn thẳng vào webcam, đưa **điểm giữa 2 lông mày** vào tâm màn hình, giữ yên ~0.3 s → đếm **3-2-1**.
3. Lần lượt **xoay đầu** (không lướt cả khuôn mặt) để đưa đúng mốc đang yêu cầu vào tâm:

   | Góc | Hành động |
   |-----|-----------|
   | Chính diện | Nhìn thẳng |
   | Ngước lên  | Ngước đầu — đưa cằm vào tâm |
   | Cúi xuống  | Cúi đầu — đưa trán vào tâm |
   | Gò má trái | Xoay đầu sang phải — đưa gò má trái vào tâm |
   | Gò má phải | Xoay đầu sang trái — đưa gò má phải vào tâm |

4. Giữ đúng ~0.3 s → app tự chụp ✅ và chuyển góc tiếp theo.
5. Đủ 5 góc → **pháo hoa** 🎉 — nhập mã SV kế tiếp hoặc thoát.

### Kết quả lưu tại

```
data/
└── faces/
    └── {student_id}/
        ├── meta.json          # id, thời gian, 5 góc, tên clip
        ├── raw/               # 5 ảnh crop JPG (center, up, down, left, right)
        └── clips/             # clip_{thời_gian}.mp4
```

---

## Chạy unit test (không cần webcam)

```bash
# uv
uv run python -m unittest discover tests

# pip
python -m unittest discover tests
```

---

## Calibrate landmark (chỉ lần đầu)

Model `2d106det` của insightface **không có tài liệu index landmark chính thức**.
Lần đầu chạy nên xác nhận các mốc đúng vị trí:

```bash
# 1. Bật chế độ debug — in số 106 landmark lên video
uv run python main.py --debug-landmarks

# 2. Nhìn vào webcam, ghi lại số điểm tương ứng với:
#    nasion (giữa 2 lông mày), nose (mũi), chin (cằm),
#    forehead (trán giữa), left_cheek, right_cheek

# 3. Ghi đè index sai vào calib_anchors.json
uv run python main.py --map nose 51
uv run python main.py --map nasion 35
```

File `calib_anchors.json` (nằm cạnh `config.py`) sẽ ghi đè index mặc định trong
`landmarks_106.py`. Nếu thiếu, app tự fallback sang landmark 68-3D.

---

## Tùy chỉnh (`config.py`)

| Hằng số | Mặc định | Ý nghĩa |
|---|---|---|
| `WEBCAM_INDEX` | `0` | Chỉ số thiết bị camera |
| `USE_GPU` | `True` | Dùng GPU nếu sẵn sàng, fallback CPU tự động |
| `CUDA_DEVICE_ID` | `0` | GPU device ID |
| `R_ALIGN` | `23` | Bán kính (px) để 1 mốc coi là "đúng tâm" |
| `R_GATE` | `90` | Bán kính nền elip gate (chống dịch cả mặt ngang) |
| `STABLE_FRAMES_ALIGN` | `10` | Số frame giữ chuẩn nasion trước khi đếm ngược |
| `STABLE_FRAMES_CAPTURE` | `8` | Số frame giữ chuẩn 1 góc trước khi chụp |
| `COUNTDOWN_SECS` | `3` | Đếm ngược 3-2-1 |
| `GAME_DETECT_SKIP` | `0` | Detect mọi frame (0 = không bỏ qua) |

---

## Cấu trúc dự án

```
├── pyproject.toml        # dependencies chính (dùng với uv)
├── requirements.txt      # dependencies cho cài pip thủ công
├── uv.lock               # lock file pinned versions (uv)
├── config.py             # webcam + GPU + hằng số game
├── main.py               # entry point app
├── main_window.py        # cửa sổ PyQt6: video + panel nhập student_id
├── camera_worker.py      # QThread: đọc webcam + detect + ghi clip
├── face_pipeline.py      # detect face, chọn face lớn nhất, lọc chất lượng
├── landmarks_106.py      # bảng anchor 106 điểm + fallback 68 + calibrate
├── game_logic.py         # state machine 5 góc (thuần Python, testable)
├── overlay.py            # VideoView: reticle, đếm ngược, pháo hoa (QPainter)
├── video_capture.py      # helper: mở webcam, tạo VideoWriter
├── tests/                # unit tests (chạy không cần webcam)
└── data/
    └── faces/            # kết quả thu theo student_id (gitignored)
```

---

## Xử lý sự cố

| Vấn đề | Cách xử lý |
|---|---|
| `uv` không phải lệnh hợp lệ | `winget install astral-sh.uv`, mở terminal mới |
| Không mở được webcam | Kiểm tra camera, đổi `WEBCAM_INDEX` trong `config.py` |
| GPU không được dùng (log: "fallback CPU") | Chạy `pip list \| findstr onnx` — nếu thấy `onnxruntime` (CPU): `pip uninstall onnxruntime -y` |
| Mốc landmark lệch vị trí | Làm bước **Calibrate landmark** phía trên |
| Chụp quá khó / không đủ 5 góc | Tăng `R_ALIGN`, tăng ánh sáng, SV ngồi gần camera hơn |
| App chậm | Đảm bảo `USE_GPU = True` trong `config.py`; thử tăng `GAME_DETECT_SKIP` (1–2) |
| Lần đầu chậm khi khởi động | Insightface đang tải model `buffalo_l` (~300 MB) — chờ 1 lần |

---

## Lưu ý

- **Dữ liệu khuôn mặt** lưu tại `data/faces/` được **gitignore** — không đẩy lên GitHub.
- **Embedding chưa lưu** — game hiện chỉ thu ảnh crop 5 góc + 1 clip; bước lưu embedding & recognition sẽ làm sau.
- Chạy qua `uv` để tránh xung đột thư viện hệ thống.
