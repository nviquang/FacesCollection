"""Entry app FaceRPG — thu thập 5 góc mặt kiểu game (PyQt6).

Chạy:
    uv run python main.py                      # chơi bình thường
    uv run python main.py --debug-landmarks    # in số landmark 106 để calibrate
    uv run python main.py --map <tên> <index>  # ghi đè 1 anchor 106 (vào calib_anchors.json)

Landmark 106 không có tài liệu index chính thức → calibrate 1 lần:
1. chạy --debug-landmarks, nhìn webcam, ghi lại số của các điểm:
   nasion, nose, chin, forehead, left_cheek, right_cheek.
2. với mỗi điểm: uv run python main.py --map nose 51 (vd).
3. chạy lại bình thường, các anchor dùng file calib.
"""
import argparse
import sys

import config


def apply_mapping(name: str, index: int) -> None:
    import landmarks_106 as lm
    data = lm.load_calib()
    data[name] = index
    lm.save_calib(data)
    print(f"Đã ghi calib: {name} -> {index}  (file: {config.CALIB_FILE})")


def run_app(debug_landmarks: bool) -> int:
    from PyQt6.QtWidgets import QApplication
    from main_window import MainWindow

    app = QApplication(sys.argv)
    win = MainWindow()
    if debug_landmarks:
        win.video.set_debug_landmarks(True)
        win._update_status("DEBUG: đang in số landmark 106. Xem terminal để map.")
    win.show()
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(description="FaceRPG — thu 5 góc mặt (PyQt6).")
    parser.add_argument("--debug-landmarks", action="store_true",
                        help="Bật overlay đánh số 106 landmark để calibrate.")
    parser.add_argument("--map", nargs=2, metavar=("TÊN", "INDEX"),
                        help="Ghi đè 1 anchor 106 vào calib_anchors.json."
                             " Tên: nasion|nose|chin|forehead|left_cheek|right_cheek.")
    args = parser.parse_args()

    if args.map is not None:
        name, raw = args.map
        valid = {"nasion", "nose", "chin", "forehead", "left_cheek", "right_cheek"}
        if name not in valid:
            print(f"TÊN không hợp lệ: {name}. Hợp lệ: {sorted(valid)}")
            return 2
        try:
            index = int(raw)
        except ValueError:
            print(f"INDEX không hợp lệ: {raw}")
            return 2
        apply_mapping(name, index)
        return 0

    config.ensure_dirs()
    return run_app(args.debug_landmarks)


if __name__ == "__main__":
    sys.exit(main())