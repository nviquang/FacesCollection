# FaceRPG UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nâng cấp giao diện PyQt6 của FaceRPG từ layout 5/6-1/6 đơn giản sang dark-tech UI rõ ràng hơn, với panel điều khiển rộng hơn, progress bar 5 góc nổi bật, overlay video sạch hơn, và visual hierarchy tốt hơn.

**Architecture:** Chỉ chỉnh sửa `main_window.py` (layout + stylesheet panel) và `overlay.py` (cải thiện draw methods cho reticle, progress, countdown). Không thay đổi logic game (`game_logic.py`), worker, pipeline, hay config. Toàn bộ là cosmetic + layout.

**Tech Stack:** PyQt6, QPainter (overlay), Python 3.11+, uv

**Spec:** Không có spec doc riêng - yêu cầu từ user: "chỉnh sửa giao diện cho app hiện tại" dùng taste skill design.

## Global Constraints

- Chạy bằng `uv run python main.py` - không thay đổi entry point
- PyQt6 (không phải PyQt5) - stylesheet syntax khác biệt quan trọng
- Không dùng thư viện animation ngoài (chỉ QTimer đã có)
- Giữ nguyên tất cả signal/slot connections và logic state machine
- Tất cả text tiếng Việt giữ nguyên
- `Optional` phải được import (`from typing import Optional`) trong `main_window.py`
- Window minimum size đủ dùng (không nhỏ hơn 1100x620)

## Review Focus

1. **Panel quá hẹp khi resize nhỏ** - stretch ratio 4:2 (thay vì 5:1) phải đảm bảo panel đủ rộng ở mọi kích thước >= minimum
2. **Màu status label mất contrast khi text dài** - `#ffd24a` trên `#16181d` OK nhưng phải test với text dài nhất ("❌ Không tạo được clip. Đợi vài giây rồi bấm Start lại.")
3. **Progress overlay che mất face detection area** - progress bar mới ở bottom của VIDEO area không được che reticle hoặc bbox
4. **Countdown số 72pt có thể bị clip** - QRectF(`cx-60, cy-40, 120, 80`) quá nhỏ cho số 72pt, phải tăng bounding rect
5. **QMessageBox stylesheet inheritance** - dialog "Đã tồn tại" kế thừa dark stylesheet có thể render lạ trên Windows

---

## File Map

| File | Loại thay đổi | Nội dung |
|------|--------------|---------|
| `main_window.py` | Modify | Layout ratio, panel stylesheet, thêm `ProgressWidget`, fix `Optional` import |
| `overlay.py` | Modify | `_draw_progress()` mới (bottom bar đẹp hơn), `_draw_countdown()` bounding rect lớn hơn, `_draw_reticle()` thêm glow effect nhẹ |

---

## Task 1: Fix import bug + nâng cấp Panel stylesheet

**Files:**
- Modify: `main_window.py` (toàn bộ `_build_panel` method + imports)

**Interfaces:**
- Produces: panel widget với layout và màu sắc mới, đúng `Optional` import

### Thay đổi design

**Layout ratio:** Đổi từ `stretch=5` / `stretch=1` sang `stretch=4` / `stretch=2` — panel chiếm 1/3 thay vì 1/6. Đủ rộng để text không bị wrap xấu.

**Màu sắc panel mới:**
- Background: `#0d0f14` (tối hơn một chút)
- Border: `#1e2130` (xanh navy nhạt thay vì xám)
- Title: `#e8edf5`, size 16px (nhỏ hơn 1 chút, gọn hơn)
- Accent: `#3b82f6` (blue-500 — sáng hơn #2d7ff9 hiện tại, đẹp hơn trên dark)
- Label: `#8b93a3`
- Body text: `#c9d1e0`
- Status text: `#facc15` (vàng ấm, dễ đọc hơn `#ffd24a`)

**Button "Bắt đầu thu thập":**
```
background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
border-radius: 7px;
padding: 10px 0;
font-size: 13px;
font-weight: 700;
letter-spacing: 0.5px;
```

**Input field:**
```
background: #0a0c11;
border: 1px solid #2a2f42;
border-radius: 6px;
padding: 8px 10px;
color: #e8edf5;
font-size: 13px;
selection-background-color: #3b82f6;
```
Focus state: `border: 1px solid #3b82f6;`

**Progress section trong panel** (THÊM MỚI - thay cho text thuần): Thêm 5 ô nhỏ hình chữ nhật (QFrame inline trong panel) hiển thị 5 góc với màu:
- Chưa chụp: `#1a1e2b` với border `#2a2f42`
- Đã chụp: `#14532d` với border `#22c55e` (xanh lá)
- Đang target hiện tại: `#1e3a5f` với border `#3b82f6` (xanh dương)

**Status area:** Tách thành 2 label riêng:
- `self.status` - trạng thái ngắn (vàng, font 12px)
- `self.target_label` - hướng dẫn hành động (trắng nhạt, font 13px, bold)

**QMessageBox override** - thêm style cho dialog xác nhận.

- [ ] **Bước 1: Thêm `Optional` import vào `main_window.py`**

Tìm dòng:
```python
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                             QPushButton, QVBoxLayout, QWidget, QMessageBox)
```
Thêm vào ngay sau phần import PyQt6:
```python
from typing import Optional
```

- [ ] **Bước 2: Đổi stretch ratio trong `__init__`**

Tìm:
```python
root.addWidget(self.video, stretch=5)   # 5/6
...
root.addWidget(panel, stretch=1)        # 1/6
```
Thay bằng:
```python
root.addWidget(self.video, stretch=4)   # 2/3
...
root.addWidget(panel, stretch=2)        # 1/3
```

- [ ] **Bước 3: Thay toàn bộ method `_build_panel`**

```python
def _build_panel(self) -> QWidget:
    panel = QFrame()
    panel.setObjectName("panel")
    panel.setStyleSheet("""
        #panel {
            background: #0d0f14;
            border: 1px solid #1e2130;
            border-radius: 10px;
        }
    """)
    lay = QVBoxLayout(panel)
    lay.setContentsMargins(16, 16, 16, 16)
    lay.setSpacing(12)

    # --- Header ---
    title = QLabel("FaceRPG")
    title.setStyleSheet(
        "font-size:16px; font-weight:700; color:#e8edf5; letter-spacing:1px;"
    )
    lay.addWidget(title)

    subtitle = QLabel("Thu 5 hướng mặt cho nhận diện sinh viên")
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet("color:#8b93a3; font-size:11px;")
    lay.addWidget(subtitle)

    # --- Divider ---
    div = QFrame()
    div.setFrameShape(QFrame.Shape.HLine)
    div.setStyleSheet("color: #1e2130;")
    lay.addWidget(div)

    # --- Student ID input ---
    sid_lbl = QLabel("MÃ SINH VIÊN")
    sid_lbl.setStyleSheet(
        "color:#5b6478; font-size:10px; font-weight:700; letter-spacing:1.5px;"
    )
    lay.addWidget(sid_lbl)

    self.sid_edit = QLineEdit()
    self.sid_edit.setPlaceholderText("VD: 2023123456")
    self.sid_edit.returnPressed.connect(self._toggle_run)
    self.sid_edit.setStyleSheet("""
        QLineEdit {
            padding: 8px 10px;
            background: #0a0c11;
            color: #e8edf5;
            border: 1px solid #2a2f42;
            border-radius: 6px;
            font-size: 13px;
            selection-background-color: #3b82f6;
        }
        QLineEdit:focus {
            border: 1px solid #3b82f6;
        }
        QLineEdit::placeholder {
            color: #3d4456;
        }
    """)
    lay.addWidget(self.sid_edit)

    # --- Start button ---
    self.btn = QPushButton("Bắt đầu thu thập")
    self.btn.clicked.connect(self._toggle_run)
    self.btn.setStyleSheet("""
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #3b82f6, stop:1 #2563eb);
            color: #ffffff;
            padding: 10px 0;
            border: none;
            border-radius: 7px;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #60a5fa, stop:1 #3b82f6);
        }
        QPushButton:pressed {
            background: #1d4ed8;
        }
        QPushButton:disabled {
            background: #1e2130;
            color: #3d4456;
        }
    """)
    lay.addWidget(self.btn)

    # --- Progress: 5 góc ---
    prog_lbl = QLabel("TIẾN TRÌNH")
    prog_lbl.setStyleSheet(
        "color:#5b6478; font-size:10px; font-weight:700; letter-spacing:1.5px;"
    )
    lay.addWidget(prog_lbl)

    self._angle_cells: dict[str, QFrame] = {}
    prog_row = QHBoxLayout()
    prog_row.setSpacing(6)
    for key, label, _ in config.ANGLES:
        cell = QFrame()
        cell.setFixedHeight(36)
        cell.setObjectName(f"angle_{key}")
        cell.setToolTip(label)
        cell.setStyleSheet("""
            QFrame {
                background: #1a1e2b;
                border: 1px solid #2a2f42;
                border-radius: 5px;
            }
        """)
        cell_lay = QVBoxLayout(cell)
        cell_lay.setContentsMargins(4, 2, 4, 2)
        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#4a5568; font-size:9px; font-weight:600;")
        lbl.setObjectName(f"anglelbl_{key}")
        cell_lay.addWidget(lbl)
        prog_row.addWidget(cell)
        self._angle_cells[key] = cell
    lay.addLayout(prog_row)

    # --- Status area ---
    self.status = QLabel("Sẵn sàng")
    self.status.setWordWrap(True)
    self.status.setStyleSheet("color:#facc15; font-size:12px;")
    lay.addWidget(self.status)

    self.target_label = QLabel()
    self.target_label.setWordWrap(True)
    self.target_label.setStyleSheet(
        "color:#e8edf5; font-size:13px; font-weight:600;"
    )
    lay.addWidget(self.target_label)

    lay.addStretch(1)

    # --- Hướng dẫn ---
    note = QLabel(
        "Hướng dẫn:\n"
        "1. Đưa giữa 2 lông mày vào tâm, giữ yên.\n"
        "2. Xoay đầu để mốc yêu cầu vào tâm.\n"
        "3. Xoay đầu - không dịch cả mặt."
    )
    note.setWordWrap(True)
    note.setStyleSheet(
        "color:#3d4456; font-size:10px; "
        "background:#0a0c11; border-radius:5px; padding:8px;"
    )
    lay.addWidget(note)

    # --- Quit button ---
    quit_btn = QPushButton("Thoát")
    quit_btn.clicked.connect(self.close)
    quit_btn.setStyleSheet("""
        QPushButton {
            background: #0f1116;
            color: #5b6478;
            padding: 7px;
            border: 1px solid #1e2130;
            border-radius: 5px;
            font-size: 12px;
        }
        QPushButton:hover {
            background: #1a1e2b;
            color: #8b93a3;
        }
    """)
    lay.addWidget(quit_btn)
    return panel
```

- [ ] **Bước 4: Thêm method `_update_angle_cells` vào `MainWindow`**

Thêm method sau `_build_panel`:
```python
def _update_angle_cells(self) -> None:
    """Cập nhật màu 5 ô tiến trình trong panel theo trạng thái session."""
    if not hasattr(self, "_angle_cells"):
        return
    current_target_key = None
    if self.session.current_target() is not None:
        current_target_key = self.session.current_target()[0]
    for key, cell in self._angle_cells.items():
        lbl = cell.findChild(QLabel, f"anglelbl_{key}")
        if key in self.session.captured:
            # Đã chụp - xanh lá
            cell.setStyleSheet("""
                QFrame {
                    background: #14532d;
                    border: 1px solid #22c55e;
                    border-radius: 5px;
                }
            """)
            if lbl:
                lbl.setStyleSheet("color:#86efac; font-size:9px; font-weight:600;")
        elif key == current_target_key:
            # Đang cần - xanh dương
            cell.setStyleSheet("""
                QFrame {
                    background: #1e3a5f;
                    border: 1px solid #3b82f6;
                    border-radius: 5px;
                }
            """)
            if lbl:
                lbl.setStyleSheet("color:#93c5fd; font-size:9px; font-weight:600;")
        else:
            # Chưa tới - mờ
            cell.setStyleSheet("""
                QFrame {
                    background: #1a1e2b;
                    border: 1px solid #2a2f42;
                    border-radius: 5px;
                }
            """)
            if lbl:
                lbl.setStyleSheet("color:#4a5568; font-size:9px; font-weight:600;")
```

- [ ] **Bước 5: Gọi `_update_angle_cells` từ `_on_frame` và `_on_event`**

Trong `_on_frame`, tìm đoạn:
```python
        # Rồi mới nạp trạng thái hiển thị từ session.
        self.video.state = self.session.state
```
Thêm ngay sau `self.video.update()`:
```python
        self._update_angle_cells()
```

Trong `_on_event`, case `"CAPTURED"` và `"DONE"` gọi thêm:
```python
        elif ev.kind == "CAPTURED":
            self._save_capture(ev.info)
            self.target_label.setText(f"Vua chup: {ev.info}")
            self._update_status("Da luu 1 goc. Tiep tuc nhe!")
            self._update_angle_cells()
        ...
        elif ev.kind == "DONE":
            self._finish_session()
            self._update_angle_cells()
```

_(Lưu ý: các event handler tiếng Việt giữ nguyên text từ code gốc - chỉ thêm `self._update_angle_cells()`)_

- [ ] **Bước 6: Reset angle cells trong `_reset_for_next`**

Tìm `_reset_for_next`, thêm vào cuối trước `return` hoặc cuối method:
```python
        self._update_angle_cells()
```

- [ ] **Bước 7: Chạy app để kiểm tra panel**

```bash
uv run python main.py
```
Kiểm tra:
- Panel chiếm khoảng 1/3 chiều rộng cửa sổ (không quá hẹp)
- 5 ô tiến trình hiển thị đủ 5 góc (Chính diện, Ngước lên, Cúi xuống, Gò má trái, Gò má phải)
- Button gradient xanh, input dark
- Text không bị wrap lạ

- [ ] **Bước 8: Commit**

```bash
git add main_window.py
git commit -m "ui: redesign control panel - wider ratio, gradient button, angle progress cells"
```

---

## Task 2: Cải thiện overlay video (reticle + countdown + progress)

**Files:**
- Modify: `overlay.py` (3 methods: `_draw_reticle`, `_draw_countdown`, `_draw_progress`)

**Interfaces:**
- Consumes: Không thay đổi interface - vẫn nhận `state`, `countdown_num`, `current_target`, `captured` từ `MainWindow`
- Produces: Overlay đẹp hơn, countdown legible hơn, progress bar thanh ngang đẹp ở bottom

### Chi tiết thay đổi

**`_draw_reticle`:** Thêm outer glow ring khi target đang reaching (vòng mờ bên ngoài vòng chính).

**`_draw_countdown`:** Tăng bounding rect từ `(cx-60, cy-40, 120, 80)` lên `(cx-80, cy-60, 160, 120)` để số 72pt không bị clip; thêm shadow effect (vẽ text đen trước, lệch 2px, rồi vẽ text màu lên trên).

**`_draw_progress`:** Thay vì text nhỏ ở góc trái, vẽ progress bar đẹp ở bottom video:
- 5 pill/capsule nhỏ nằm ngang, căn giữa bottom
- Mỗi pill: rộng ~70px, cao ~20px, border-radius ~10
- Màu: done=xanh lá, current=xanh dương pulse, todo=trắng mờ
- Text label nhỏ bên trong pill

- [ ] **Bước 1: Cải thiện `_draw_reticle` - thêm glow khi đang reaching**

Tìm nguyên method `_draw_reticle` và thay toàn bộ:
```python
def _draw_reticle(self, painter: QPainter) -> None:
    cx, cy = self._center
    reaching = self._target_reaching()
    r = config.R_ALIGN * self._scale

    # Outer glow ring khi đang reaching (vẽ trước để bị đè)
    if reaching:
        glow_color = QColor(0, 255, 120, 40)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow_color)
        painter.drawEllipse(QRectF(cx - r * 1.6, cy - r * 1.6,
                                    r * 3.2, r * 3.2))
        glow_color2 = QColor(0, 255, 120, 20)
        painter.setBrush(glow_color2)
        painter.drawEllipse(QRectF(cx - r * 2.2, cy - r * 2.2,
                                    r * 4.4, r * 4.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    # Vòng R_ALIGN chính
    color = QColor(0, 255, 120) if reaching else QColor(240, 70, 70)
    pen = QPen(color, 2)
    painter.setPen(pen)
    painter.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))

    # Elip gate xoay (chỉ lúc COLLECT)
    if self.state == COLLECT and self._packet is not None and self._packet.bbox is not None:
        x1, y1, x2, y2 = self._packet.bbox
        bw, bh = (float(x2) - float(x1)), (float(y2) - float(y1))
        rxg = max(config.R_GATE, config.R_GATE_SCALE_X * bw) * self._scale
        ryg = max(config.R_GATE, config.R_GATE_SCALE_Y * bh) * self._scale
        painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
        painter.drawEllipse(QRectF(cx - rxg, cy - ryg, 2 * rxg, 2 * ryg))

    # Dấu cộng tâm - 4 đoạn ngắn với gap ở giữa
    painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
    gap = 5
    arm = 12
    painter.drawLine(QPointF(cx - arm - gap, cy), QPointF(cx - gap, cy))
    painter.drawLine(QPointF(cx + gap, cy), QPointF(cx + arm + gap, cy))
    painter.drawLine(QPointF(cx, cy - arm - gap), QPointF(cx, cy - gap))
    painter.drawLine(QPointF(cx, cy + gap), QPointF(cx, cy + arm + gap))
    # Chấm tâm nhỏ
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 200))
    painter.drawEllipse(QRectF(cx - 2, cy - 2, 4, 4))
    painter.setBrush(Qt.BrushStyle.NoBrush)
```

- [ ] **Bước 2: Cải thiện `_draw_countdown` - bounding rect lớn hơn + shadow**

Tìm nguyên method `_draw_countdown` và thay toàn bộ:
```python
def _draw_countdown(self, painter: QPainter) -> None:
    if self.state != COUNTDOWN or self.countdown_num <= 0:
        return
    cx, cy = self._center
    num_str = str(self.countdown_num)

    # Shadow (vẽ trước, lệch xuống phải)
    f_shadow = QFont(painter.font())
    f_shadow.setPointSize(72)
    f_shadow.setBold(True)
    painter.setFont(f_shadow)
    painter.setPen(QColor(0, 0, 0, 150))
    painter.drawText(
        QRectF(cx - 78, cy - 58, 160, 120),
        Qt.AlignmentFlag.AlignCenter,
        num_str,
    )

    # Text chính - vàng sáng
    f = QFont(painter.font())
    f.setPointSize(72)
    f.setBold(True)
    painter.setFont(f)
    painter.setPen(QColor(250, 204, 21))
    painter.drawText(
        QRectF(cx - 80, cy - 60, 160, 120),
        Qt.AlignmentFlag.AlignCenter,
        num_str,
    )
```

- [ ] **Bước 3: Thay `_draw_progress` - progress pills đẹp ở bottom**

Tìm nguyên method `_draw_progress` và thay toàn bộ:
```python
def _draw_progress(self, painter: QPainter) -> None:
    if not self.angle_defs:
        return

    # Kích thước pill
    pill_w = 72
    pill_h = 22
    pill_r = 11      # border-radius
    spacing = 8
    total_w = len(self.angle_defs) * pill_w + (len(self.angle_defs) - 1) * spacing
    start_x = (self.width() - total_w) / 2
    y = self.height() - pill_h - 12

    current_key = None
    if self.current_target is not None:
        current_key = self.current_target[0]

    painter.setFont(QFont(painter.font().family(), 8))
    fm = painter.fontMetrics()

    for i, (key, label, _) in enumerate(self.angle_defs):
        x = start_x + i * (pill_w + spacing)
        rect = QRectF(x, y, pill_w, pill_h)
        done = key in self.captured
        is_current = (key == current_key)

        if done:
            # Xanh lá
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(20, 83, 45, 200))
            painter.drawRoundedRect(rect, pill_r, pill_r)
            painter.setPen(QPen(QColor(34, 197, 94, 180), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, pill_r, pill_r)
            painter.setPen(QColor(134, 239, 172))
        elif is_current:
            # Xanh dương - đang cần
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(30, 58, 95, 220))
            painter.drawRoundedRect(rect, pill_r, pill_r)
            painter.setPen(QPen(QColor(59, 130, 246, 200), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, pill_r, pill_r)
            painter.setPen(QColor(147, 197, 253))
        else:
            # Mờ - chưa tới
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(20, 24, 36, 160))
            painter.drawRoundedRect(rect, pill_r, pill_r)
            painter.setPen(QPen(QColor(60, 68, 90, 150), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, pill_r, pill_r)
            painter.setPen(QColor(75, 85, 110))

        # Label text căn giữa pill (truncate nếu dài)
        display = label if fm.horizontalAdvance(label) < pill_w - 8 else label[:5] + ".."
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, display)
```

- [ ] **Bước 4: Chạy app kiểm tra overlay**

```bash
uv run python main.py
```
Kiểm tra:
- Reticle có glow ring màu xanh lá khi mốc vào tâm
- Dấu cộng tâm có gap ở giữa (gap reticle style)
- Progress pills 5 góc ở dưới cùng khung video, căn giữa
- Countdown số to, không bị clip, có shadow nhẹ

- [ ] **Bước 5: Commit**

```bash
git add overlay.py
git commit -m "ui: improve video overlay - glow reticle, better countdown, pill progress bar"
```

---

## Task 3: Style toàn cục + window background + QMessageBox

**Files:**
- Modify: `main.py` (thêm global app stylesheet)
- Modify: `main_window.py` (`_start_session` - style QMessageBox)

**Interfaces:**
- Consumes: QApplication từ `main.py`
- Produces: Window background tối, QMessageBox dark theme

- [ ] **Bước 1: Thêm global stylesheet vào `main.py` sau `app = QApplication(sys.argv)`**

Tìm trong `run_app`:
```python
    app = QApplication(sys.argv)
    win = MainWindow()
```
Thêm stylesheet vào giữa:
```python
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QMainWindow, QWidget#central {
            background: #080a0f;
        }
        QToolTip {
            background: #0d0f14;
            color: #c9d1e0;
            border: 1px solid #2a2f42;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
        }
        QScrollBar:vertical {
            background: #0a0c11;
            width: 6px;
            border-radius: 3px;
        }
        QScrollBar::handle:vertical {
            background: #2a2f42;
            border-radius: 3px;
            min-height: 20px;
        }
    """)
    win = MainWindow()
```

- [ ] **Bước 2: Style QMessageBox trong `_start_session` của `main_window.py`**

Tìm `_start_session`, tìm đoạn:
```python
            ans = QMessageBox.question(
                self, "Đã tồn tại",
                f"{sid} đã có dữ liệu. Xoá dữ liệu cũ và bắt đầu lại?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
```
Thay bằng:
```python
            msg = QMessageBox(self)
            msg.setWindowTitle("Đã tồn tại")
            msg.setText(f"{sid} đã có dữ liệu. Xoá dữ liệu cũ và bắt đầu lại?")
            msg.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            msg.setStyleSheet("""
                QMessageBox {
                    background: #0d0f14;
                    color: #e8edf5;
                }
                QMessageBox QLabel {
                    color: #e8edf5;
                    font-size: 13px;
                }
                QPushButton {
                    background: #1a1e2b;
                    color: #c9d1e0;
                    border: 1px solid #2a2f42;
                    border-radius: 5px;
                    padding: 6px 16px;
                    font-size: 12px;
                    min-width: 60px;
                }
                QPushButton:hover {
                    background: #2a2f42;
                    color: #e8edf5;
                }
                QPushButton[text="&Yes"] {
                    background: #1e3a5f;
                    border-color: #3b82f6;
                    color: #93c5fd;
                }
                QPushButton[text="&Yes"]:hover {
                    background: #2563eb;
                    color: #ffffff;
                }
            """)
            ans = msg.exec()
            if ans != QMessageBox.StandardButton.Yes:
```

_(Lưu ý: `msg.exec()` trả về int — so sánh với `QMessageBox.StandardButton.Yes.value` nếu cần, hoặc import và cast. Test để chắc chắn.)_

- [ ] **Bước 3: Set central widget objectName để stylesheet match**

Trong `MainWindow.__init__`, tìm:
```python
        central = QWidget()
        self.setCentralWidget(central)
```
Thêm:
```python
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
```

- [ ] **Bước 4: Chạy app kiểm tra toàn bộ**

```bash
uv run python main.py
```
Kiểm tra end-to-end:
- Nhập mã SV → bấm Start → thấy 5 ô panel cells đổi màu xanh dương ô đang cần
- Xoay đầu → reticle glow khi vào tâm
- Sau khi chụp → ô đó chuyển xanh lá
- Nhập SV đã có → QMessageBox dark theme
- Thoát app bình thường

- [ ] **Bước 5: Commit**

```bash
git add main.py main_window.py
git commit -m "ui: global dark stylesheet, dark QMessageBox, central widget objectName"
```

---

## Tổng kết thay đổi

| Hạng mục | Trước | Sau |
|---|---|---|
| Panel width | 1/6 (~183px) | 1/3 (~367px) |
| Progress | Text nhỏ góc video | 5 pills màu trong panel + overlay bottom |
| Reticle | Vòng tròn đơn | Vòng + glow khi aligned |
| Countdown | Số vàng, có thể clip | Số vàng + shadow, rect đủ lớn |
| Button | Flat blue | Gradient blue với hover/pressed states |
| Input | Basic dark | Dark với focus ring xanh |
| Window bg | Mặc định Qt | `#080a0f` dark |
| QMessageBox | Default Qt light | Dark themed |
| `Optional` import | Thiếu (bug) | Có |
