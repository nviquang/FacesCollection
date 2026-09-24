"""Cửa sổ chính FaceRPG: video 5/6 trái + panel 1/6 phải (id SV + Start).

Nối: CaptureWorker (QThread) → FramePacket signal → VideoView + GameSession.
Khi Start: tạo folder data/faces/{sid}, ghi meta, bật clip, session.start().
Khi event DONE: chụp xong 5 góc → VideoView.trigger_celebration(mũi) + log.
Khi CAPTURED: worker tự lưu crop ảnh? — ở đây MainWindow nhận key, lưu ảnh crop
từ frame cuối (packet mới nhất có face) qua face_pipeline.crop_face + quality.
"""
import datetime
import json
import logging
import shutil

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                             QPushButton, QVBoxLayout, QWidget, QMessageBox)

import config
import face_pipeline
from game_logic import (ALIGN_NASION, CELEBRATE, COLLECT, COUNTDOWN, IDLE,
                        GameEvent, GameSession, FrameState)
from camera_worker import CaptureWorker
from landmarks_106 import LandmarkSource
from overlay import VideoView

# Crop ảnh fallback nhỏ hơn ngưỡng này mỗi chiều → coi là không hợp lệ (tiny/blog).
MIN_CROP_SIDE = 20


class MainWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("FaceRPG — Thu thập 5 góc mặt")
        self.resize(1100, 620)

        self.worker: Optional[CaptureWorker] = None
        self.session = GameSession(self._on_event)
        self._lm = LandmarkSource()
        self._last_status_state = None

        # UI
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.video = VideoView()
        root.addWidget(self.video, stretch=5)   # 5/6

        panel = self._build_panel()
        root.addWidget(panel, stretch=1)        # 1/6

        self._start_worker()
        self._update_status(self._session_state_text())

    # ------------------------------------------------------------------ #
    def _build_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setStyleSheet(
            "#panel { background:#16181d; border:1px solid #2a2d36; border-radius:8px; }"
        )
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        title = QLabel("FaceRPG")
        title.setStyleSheet("font-size:18px; font-weight:700; color:#fff;")
        lay.addWidget(title)

        info = QLabel("Thu 5 hướng mặt: chính diện, ngước lên, cúi xuống, gò má trái/phải.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#cfd3dc; font-size:12px;")
        lay.addWidget(info)

        lay.addSpacing(6)
        lay.addWidget(QLabel("Mã sinh viên"))
        self.sid_edit = QLineEdit()
        self.sid_edit.setPlaceholderText("VD: 2023123456")
        self.sid_edit.returnPressed.connect(self._toggle_run)
        self.sid_edit.setStyleSheet("padding:6px; background:#0f1116; color:#fff;"
                                    "border:1px solid #333; border-radius:5px;")
        lay.addWidget(self.sid_edit)

        self.btn = QPushButton("Bắt đầu thu thập")
        self.btn.clicked.connect(self._toggle_run)
        self.btn.setStyleSheet(
            "QPushButton { background:#2d7ff9; color:#fff; padding:10px; border:none;"
            " border-radius:6px; font-weight:600; }"
            "QPushButton:hover { background:#3a8aff; }"
            "QPushButton:disabled { background:#444; }")
        lay.addWidget(self.btn)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#ffd24a; font-size:13px;")
        lay.addWidget(self.status)

        self.target_label = QLabel()
        self.target_label.setWordWrap(True)
        self.target_label.setStyleSheet("color:#e8edf5; font-size:13px;")
        lay.addWidget(self.target_label)

        lay.addStretch(1)

        note = QLabel("Hướng dẫn:\n• Đưa giữa 2 lông mày vào tâm màn hình, giữ yên.\n"
                      "• Quay đầu để mốc được yêu cầu rơi vào tâm.\n"
                      "• Xoay đầu KHÔNG di chuyển cả mặt.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#8b93a3; font-size:11px;")
        lay.addWidget(note)

        quit_btn = QPushButton("Thoát")
        quit_btn.clicked.connect(self.close)
        quit_btn.setStyleSheet(
            "QPushButton { background:#3a3f4b; color:#fff; padding:8px;"
            " border:none; border-radius:5px; }"
            "QPushButton:hover { background:#4a4f5b; }")
        lay.addWidget(quit_btn)
        return panel

    # ------------------------------------------------------------------ #
    def _start_worker(self) -> None:
        self.worker = CaptureWorker(self._lm)
        self.worker.frameReady.connect(self._on_frame)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    def _on_frame(self, pk) -> None:
        self.video.set_packet(pk)
        if pk is not None and pk.frame_bgr is not None:
            h, w = pk.frame_bgr.shape[:2]
            self.session.set_center(w / 2.0, h / 2.0)
        # Bơm frame vào logic trước — session có thể đổi state (→ event CAPTURED/DONE).
        if self.session.state not in (IDLE, CELEBRATE):
            self.session.inject_frame(FrameState(points=pk.points, frame_bgr=pk.frame_bgr,
                                                 face=pk.face, bbox=pk.bbox,
                                                 face_ok=pk.face_ok))
        # Rồi mới nạp trạng thái hiển thị từ session.
        self.video.state = self.session.state
        self.video.countdown_num = self.session._last_count
        self.video.current_target = self.session.current_target()
        self.video.captured = list(self.session.captured)
        self.video.update()
        # Refresh status generic chỉ khi state đổi (tránh đè message cụ thể như "Đã chụp").
        if self.session.state != self._last_status_state:
            self._last_status_state = self.session.state
            self._update_status(self._session_state_text())

    def _on_event(self, ev: GameEvent) -> None:
        # Called from session (main thread) during inject_frame.
        if ev.kind == "COUNTDOWN":
            self.video.countdown_num = ev.info
            self._update_status(f"Bắt đầu thu sau: {ev.info}")
        elif ev.kind == "NEED_TARGET":
            label = ev.info["label"]
            self.target_label.setText(f"🎯 Quay đầu để đưa điểm sau vào tâm màn hình:\n{label}")
            self._update_status("Hãy xoay đầu — không dịch chuyển cả khuôn mặt.")
        elif ev.kind == "CAPTURED":
            self._save_capture(ev.info)
            self.target_label.setText(f"✅ Đã chụp: {ev.info}")
            self._update_status("Đã lưu 1 góc. Tiếp tục nhé!")
        elif ev.kind == "HOLD_FAIL":
            self._update_status(ev.info)
        elif ev.kind == "DONE":
            self._finish_session()
        elif ev.kind == "ALIGNING":
            self.target_label.setText("Điểm giữa 2 lông mày → đưa vào tâm rồi giữ yên.")
            self._update_status("Nhìn chính diện camera, nâng/điều chỉnh để giữa lông mày ở tâm.")

    def _save_capture(self, key: str) -> None:
        """Lưu crop ảnh của góc `key` từ frame packet mới nhất."""
        if self.worker is None:
            return
        pk = self.video._packet
        if pk is None or pk.face is None:
            return
        raw_dir = self._out_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        path = raw_dir / f"{key}_{ts}.jpg"
        ok = self.worker.save_crop_if_ok(pk.frame_bgr, pk.face, path)
        print(f"[save] {key} -> {path} ({'ok' if ok else 'kém nét — thử ghi fallback?'})")
        # Nếu kém nét vẫn thử ghi fallback (lưu nhiều hơn để không mất góc) —
        # nhưng phải kiểm tra crop thực sự hợp lệ trước khi ghi, không ghi bừa.
        if not ok:
            import cv2
            crop = face_pipeline.crop_face(pk.frame_bgr, pk.face)
            if (crop is None or len(crop.shape) != 3
                    or crop.shape[0] < MIN_CROP_SIDE or crop.shape[1] < MIN_CROP_SIDE):
                print(f"[save] {key} fallback SKIP — crop không hợp lệ (quá nhỏ/sát mép): {path}")
                self._update_status("⚠️ Crop lỗi — kiểm tra khuôn mặt rồi thử lại.")
                return
            wrote = cv2.imwrite(str(path), crop)
            if not wrote:
                print(f"[save] {key} fallback LỖI ghi ảnh: {path}")
                self._update_status("⚠️ Không ghi được ảnh — kiểm tra ổ đĩa.")
                return
            print(f"[save] {key} fallback -> {path}")

    def _finish_session(self) -> None:
        self.target_label.setText("🎉 Chúc mừng! Bạn đã thu đủ 5 góc mặt!")
        self._update_status("Đã lưu 5 góc. Nhập SV kế tiếp để chơi tiếp.")
        # Pháo hoa tại điểm mũi (frame coords).
        origin = (0.0, 0.0)
        if self.video._packet is not None and "center" in self.video._packet.points:
            origin = self.video._packet.points["center"]
        self.video.trigger_celebration(origin)
        self._save_meta()
        # Session không có clip (start_clip chưa tạo được writer) → xoá cả folder
        # dữ liệu mới tạo để không để lại mớ folder rỗng khiến meta không khớp.
        out = getattr(self, "_out_dir", None)
        if out is not None and self.worker is not None:
            clip = self.worker.clip_path()
            if clip is None and out.exists():
                shutil.rmtree(out, ignore_errors=True)
            self._out_dir = None
        self._reset_for_next()

    def _save_meta(self) -> None:
        out = getattr(self, "_out_dir", None)
        if out is None:
            return
        meta = {
            "student_id": self.session.student_id,
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "angles": self.session.captured,
            "num_angles": len(self.session.captured),
            "clip_file": self.worker.clip_path().name if self.worker and self.worker.clip_path() else None,
            "source": "webcam",
            "device": f"webcam_index={config.WEBCAM_INDEX}",
            "provider": ("cuda" if self.worker.detector and self.worker.detector.ctx_id >= 0 else "cpu"),
            "note": "5 góc mặt cho embedding/recognition (game FaceRPG).",
        }
        try:
            with open(out / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"Cảnh báo: không ghi được meta: {e}")

    def _reset_for_next(self) -> None:
        # Đóng clip + đưa session về IDLE để Start SV kế hoạt động bình thường.
        if self.worker:
            self.worker.stop_clip()
        self.session.reset()
        self.video.state = IDLE
        self.video.captured = []
        self.video.countdown_num = 0
        self.btn.setText("Bắt đầu thu thập")
        self.btn.setEnabled(True)
        self._update_status("Sẵn sàng. Nhập mã SV mới để bắt đầu.")

    # ------------------------------------------------------------------ #
    def _toggle_run(self) -> None:
        if self.session.state == IDLE:
            sid = face_pipeline.sanitize(self.sid_edit.text().strip())
            if not sid:
                self._update_status("Nhập mã sinh viên (chữ số/chữ/_/-).")
                return
            self._start_session(sid)
        else:
            self._cancel_session()

    def _start_session(self, sid: str) -> None:
        out = config.FACES_DIR / sid
        if out.exists():
            ans = QMessageBox.question(
                self, "Đã tồn tại",
                f"{sid} đã có dữ liệu. Xoá dữ liệu cũ và bắt đầu lại?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                self._update_status("Đổi mã SV hoặc bấm lại.")
                return
            shutil.rmtree(out, ignore_errors=True)
        (out / "raw").mkdir(parents=True, exist_ok=True)
        (out / "clips").mkdir(parents=True, exist_ok=True)
        # Chưa đặt _out_dir — chỉ gán khi clip TẠO ĐƯỢC (meta.json chỉ ghi cho
        # session thật sự chạy).
        if self.worker:
            clip_ok = self.worker.start_clip(out / "clips")
            if clip_ok is None:
                # start_clip trả None khi webcam chưa mở (self.cap chưa có) hoặc
                # make_writer thất bại → KHÔNG bắt đầu session, tránh chạy mò mẫm
                # không clip mà không ai biết.
                self._update_status("❌ Không tạo được clip. Đợi vài giây rồi bấm Start lại.")
                shutil.rmtree(out, ignore_errors=True)
                return
        self._out_dir = out
        self.session.start(sid)
        self.btn.setText("Hủy bỏ (đang thu)")
        self.target_label.setText("Chuẩn bị...")
        self._update_status("Đưa giữa 2 lông mày vào tâm màn hình rồi giữ yên...")

    def _cancel_session(self) -> None:
        self.session.reset()
        if self.worker:
            self.worker.stop_clip()
        self.btn.setText("Bắt đầu thu thập")
        self.target_label.setText("")
        self._update_status("Đã hủy. Nhập mã SV mới để bắt đầu.")
        self.video.captured = []
        self.video.state = IDLE

    def _update_status(self, text: str) -> None:
        self.status.setText(text)

    def _session_state_text(self) -> str:
        return {"IDLE": "Sẵn sàng", ALIGN_NASION: "Đưa giữa lông mày vào tâm",
                COUNTDOWN: "Đếm ngược...", COLLECT: "Thu góc...", CELEBRATE: "Chúc mừng!"}.get(
            self.session.state, self.session.state)

    def _on_worker_error(self, msg: str) -> None:
        self._update_status(f"❌ {msg}")

    # ------------------------------------------------------------------ #
    def closeEvent(self, ev) -> None:
        if self.worker is not None:
            self.worker.stop()
            # Chờ worker thoát theo nhịp nhỏ, kiểm tra từng lần trả về — worker có
            # thể kẹt bên trong cap.read()/detect (hay gặp trên Windows) và chỉ
            # nhả sau vài giây chứ không dừng tức thì.
            waited = 0
            step = 250   # ms
            total = 5000  # ~5s chờ tối đa theo bước nhỏ
            while waited < total:
                if self.worker.wait(step):
                    break
                waited += step
            else:
                # Thread vẫn còn chạy sau 5s: app đang thoát, worker chỉ sở hữu
                # webcam + writer — terminate để không rơi vào
                # "QThread: Destroyed while thread is still running" (abort/hang).
                logging.warning("CaptureWorker vẫn chạy sau 5s khi thoát — dùng terminate() để dọn.")
                self.worker.stop()
                self.worker.terminate()
                self.worker.wait()
        super().closeEvent(ev)