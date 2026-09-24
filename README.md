# DataCollectionForLMS — FaceRPG

Thu thập dữ liệu khuôn mặt sinh viên phục vụ nhận diện trong lớp (recognition).
App **PyQt6** biến việc thu thành một trò chơi: người dùng **xoay đầu** để đưa từng
mốc trên mặt (giữa 2 lông mày, mũi, cằm, trán, gò má trái/phải) vào **đúng tâm**
màn hình. Ghép đủ **5 góc mục tiêu** thì auto-chụp từng góc (1 ảnh/góc) + ghi
**1 clip** toàn quá trình, lưu theo `student_id`.

> Thay thế hoàn toàn CLI cũ (`collect_faces.py` đã bị xoá).

---

## Yêu cầu

- **Windows 10/11** (đã chạy thử trên Windows 11)
- **uv** — quản lý môi trường ảo + dependencies. Cài: `winget install astral-sh.uv`
- **Webcam** máy tính (chỉ số mặc định `0`)
- Python được uv tự tải/cài nếu chưa có

---

## Cài đặt

```bash
uv sync
```

> Lần đầu sẽ cài `opencv`, `insightface`, `onnxruntime`, **`pyqt6`**, v.v. vào `.venv`
> — không làm bẩn Python hệ thống.

---

## Sử dụng

```bash
uv run python main.py
```

**Luồng chơi:**

1. Nhập `student_id` (vd `2023123456`) ở panel phải, bấm **Bắt đầu thu thập**.
2. Nhìn chính diện webcam: **đưa điểm giữa 2 lông mày vào tâm màn hình rồi giữ yên**.
   Giữ chuẩn ~0.3s → màn hình đếm **3-2-1**.
3. Lần lượt **xoay đầu** (đừng trượt cả khuôn mặt) để đưa đúng mốc đang được yêu cầu
   vào tâm (mũi → cằm → trán → gò má trái → gò má phải). Khi giữ đúng ~0.3s, app
   tự chụp ✅ và chuyển sang góc kế.
4. Đủ 5 góc → một **đốm đỏ** nổ từ mũi thành **pháo hoa** + chúc mừng 🎉.
5. Nhập mã SV kế tiếp hoặc thoát.

**Phím / thao tác:**
- Bấm **Hủy bỏ** (nút Start khi đang chạy) để hủy giữa chừng.
- Ghi **1 clip** mp4 toàn quá trình trong lúc chơi (từ lúc bấm Start đến hết 5 góc).

**Kết quả lưu tại:**

```
data/faces/{student_id}/
├── meta.json             # id, thời gian, 5 góc, clip, nguồn
├── raw/                  # 5 ảnh crop khuôn mặt (JPG) theo góc: nose_, chin_, forehead_, left_cheek_, right_cheek_
└── clips/                # clip_{thời_gian}.mp4
```

---

## Calibrate landmark (chỉ lần đầu, model 106 điểm)

Model `2d106det` của insightface **không có tài liệu index chính thức**. Lần đầu
chạy hãy xác nhận các mốc có khớp:

```bash
# 1. In số 106 landmark lên video
uv run python main.py --debug-landmarks

# 2. Nhìn webcam, ghi lại số của các điểm:
#    nasion (giữa 2 lông mày), nose (mũi), chin (cằm),
#    forehead (trán giữa), left_cheek (gò má trái), right_cheek (gò má phải)

# 3. Với từng điểm lệch, ghi đè index vào file calib_anchors.json
uv run python main.py --map nose 51
uv run python main.py --map nasion 35

# 4. Chạy lại bình thường
uv run python main.py
```

File `calib_anchors.json` (nằm cạnh `config.py`) sẽ ghi đè index mặc định trong
`landmarks_106.py`. Nếu thiếu anchor, `landmarks_106.py` tự fallback sang landmark
68-3D (index chuẩn: cằm=8, mũi=30, giữa 2 mày = midpoint(21,22)).

---

## Cấu trúc

```
├── pyproject.toml        # deps do uv quản lý
├── config.py             # webcam + GPU + hằng số game (ngưỡng, 5 góc)
├── video_capture.py      # helper: mở webcam, tạo VideoWriter
├── face_pipeline.py      # detect + chọn face + lọc chất lượng (giữ nguyên)
├── landmarks_106.py      # bảng anchor 106 + fallback 68 + calibrate
├── game_logic.py         # state machine thuần Python (test được, không Qt)
├── camera_worker.py      # QThread: webcam + detect + ghi clip
├── overlay.py            # VideoView: reticle, đếm ngược, pháo hoa (QPainter)
├── main_window.py        # cửa sổ: video 5/6 + panel phải 1/6
├── main.py               # entry app
├── tests/
│   └── test_game_logic.py  # unit test logic game (chạy không cần webcam)
└── data/
    └── faces/            # theo student_id: raw/, clips/, meta.json
```

---

## Tùy chỉnh (config.py)

| Hằng số | Mặc định | Ý nghĩa |
|---|---|---|
| `R_ALIGN` | 34 | Bán kính (px) để 1 mốc coi là "đúng tâm" |
| `R_GATE` | 90 | Bán kính nasion quanh tâm chứng minh XOAY ĐẦU (chống dịch mặt) |
| `STABLE_FRAMES_ALIGN` | 10 | Số frame giữ chuẩn nasion trước khi đếm ngược |
| `STABLE_FRAMES_CAPTURE` | 8 | Số frame giữ chuẩn 1 góc trước khi chụp |
| `COUNTDOWN_SECS` | 3 | Đếm ngược 3-2-1 |
| `ANGLES` | 5 góc | Thứ tự & nhãn các góc thu |

---

## Xử lý sự cố

| Vấn đề | Cách xử lý |
|---|---|
| `uv` không phải lệnh hợp lệ | `winget install astral-sh.uv`, mở terminal mới |
| Không mở được webcam | Kiểm tra camera, đổi `WEBCAM_INDEX` trong `config.py` |
| Mốc landmark lệch vị trí | Làm bước **Calibrate landmark** phía trên |
| Chụp không đủ 5 góc / quá khó | Tăng `R_ALIGN`, tăng ánh sáng, cho SV ngồi gần camera |
| App chậm khi bật video | Để GPU: `USE_GPU` trong `config.py`; nếu vẫn chậm có thể tăng `GAME_DETECT_SKIP` (bỏ qua frame — landmark bám kém mượt hơn) |