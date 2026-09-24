"""Unit test cho game_logic.GameSession (không cần webcam/Qt).

Chạy: uv run python -m unittest discover tests
"""
import unittest

from game_logic import (ALIGN_NASION, CELEBRATE, COLLECT, COUNTDOWN, IDLE,
                        FrameState, GameEvent, GameSession)


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def make_session(**kw_max):
    evs = []
    clock = FakeClock()
    kw = dict(r_align=10, r_gate=40, stable_align=3, stable_capture=3,
              countdown=1.0)
    if kw_max is not None:
        kw.update(kw_max)  # kw_max đè giá trị mặc định (vd stable_capture=0)
    s = GameSession(lambda e: evs.append(e), clock=clock, **kw)
    s.set_center(320, 240)
    return s, evs, clock


def pts(nasion=None, nose=None, chin=None, forehead=None, left_cheek=None, right_cheek=None):
    d = {}
    for k, v in [("nasion", nasion), ("nose", nose), ("chin", chin),
                 ("forehead", forehead), ("left_cheek", left_cheek),
                 ("right_cheek", right_cheek)]:
        if v is not None:
            d[k] = v
    return d


BIG_BBOX = (100.0, 50.0, 500.0, 400.0)  # mặt to, gần camera (chơi game điển hình)


class TestFrameState(unittest.TestCase):
    def test_accepts_frame_bgr_and_face_kwargs(self):
        """main_window._on_frame bơm FrameState(points=..., frame_bgr=...,
        face=..., bbox=..., face_ok=...) — cả 5 phải là field của dataclass
        (dataclass chỉ nhận kwarg cho field CÓ type annotation)."""
        fake_frame = object()
        fake_face = object()
        fs = FrameState(points=pts(nasion=(1.0, 2.0)), frame_bgr=fake_frame,
                        face=fake_face, bbox=BIG_BBOX, face_ok=True)
        self.assertIs(fs.frame_bgr, fake_frame)
        self.assertIs(fs.face, fake_face)
        self.assertEqual(fs.bbox, BIG_BBOX)
        self.assertTrue(fs.face_ok)


class TestAlign(unittest.TestCase):
    def test_nasion_enter(self):
        s, evs, _ = make_session()
        s.start("12A")
        self.assertEqual(s.state, ALIGN_NASION)
        # giữa lông mày chưa vào tâm → không advance
        s.inject_frame(FrameState(points=pts(nasion=(200.0, 100.0))))
        self.assertEqual(s.state, ALIGN_NASION)
        self.assertEqual(s._hold_align, 0)

    def test_nasion_hold_promotes(self):
        s, evs, clock = make_session()
        s.start("A")
        for _ in range(3):
            s.inject_frame(FrameState(points=pts(nasion=(320.0, 240.0))))
        self.assertEqual(s.state, COUNTDOWN)
        self.assertEqual(evs[0].kind, "ALIGNING")

    def test_hold_fail_resets(self):
        s, evs, _ = make_session()
        s.start("A")
        s.inject_frame(FrameState(points=pts(nasion=(320.0, 240.0))))  # +1
        s.inject_frame(FrameState(points=pts(nasion=(320.0, 240.0))))  # +2
        s.inject_frame(FrameState(points=pts(nasion=(500.0, 100.0))))  # reset, HOLD_FAIL
        self.assertEqual(s._hold_align, 0)
        self.assertTrue(any(e.kind == "HOLD_FAIL" for e in evs))


class TestCountdown(unittest.TestCase):
    def test_countdown_events(self):
        s, evs, clock = make_session()
        s.start("A")
        for _ in range(3):
            s.inject_frame(FrameState(points=pts(nasion=(320.0, 240.0))))
        self.assertEqual(s.state, COUNTDOWN)
        n = len(evs)
        clock.t += 0.4
        s.inject_frame(FrameState(points=pts(nasion=(320.0, 240.0))))  # remaining 1
        self.assertEqual(evs[-1].kind, "COUNTDOWN")
        clock.t += 0.8  # đã qua 1.0s
        s.inject_frame(FrameState(points=pts(nasion=(320.0, 240.0))))
        self.assertEqual(s.state, COLLECT)
        # trước khi collect → NEED_TARGET
        self.assertEqual(evs[-1].kind, "NEED_TARGET")


class TestCollect(unittest.TestCase):
    def _to_collect(self, s, clock):
        """Đưa session tới COLLECT (target 1 = nose) nhưng CHƯA chụp target nào."""
        for _ in range(3):
            s.inject_frame(FrameState(points=pts(nasion=(320.0, 240.0))))
        clock.t += 1.2
        s.inject_frame(FrameState(points=pts(nasion=(320.0, 240.0))))
        self.assertEqual(s.state, COLLECT)

    def test_full_run(self):
        s, evs, clock = make_session()
        s.start("A")
        self._to_collect(s, clock)
        # target 1 = nose: mũi vào tâm, nasion sát tâm.
        for _ in range(3):
            s.inject_frame(FrameState(points=pts(nasion=(320.0, 238.0),
                                                 nose=(320.0, 240.0))))
        self.assertEqual(s.captured, ["nose"])
        self.assertEqual(s.target_index, 1)
        self.assertEqual(evs[-2].kind, "CAPTURED")
        self.assertEqual(evs[-1].kind, "NEED_TARGET")  # sang target 2

    def test_translation_small_face_rejected(self):
        """Mặt NHỎ (xa camera): gate co về vòng tròn floor → trượt cả mặt để
        mũi vào tâm (nasion lệch ~50px) bị chặn."""
        s, evs, clock = make_session()
        s.start("A")
        self._to_collect(s, clock)
        small = (300.0, 220.0, 340.0, 260.0)   # bw=40 → rx=ry=floor 40
        for _ in range(5):
            s.inject_frame(FrameState(points=pts(nasion=(320.0, 190.0),  # dy 50 > 40
                                                 nose=(320.0, 240.0)),
                                      bbox=small))
        self.assertNotIn("nose", s.captured)
        self.assertEqual(s._hold_capture, 0)

    def test_deep_rotation_allowed_big_face(self):
        """Hồi quy: ngước lên để đưa CẰM vào tâm → nasion lệch trên ~130px.
        Với mặt TO gần camera, gate là elip mở rộng theo bbox → CHO PHÉP
        (trước đây bị vòng tròn tuyệt đối 85px chặn = không chụp được cằm)."""
        s, evs, clock = make_session()
        s.start("A")
        self._to_collect(s, clock)
        self.assertEqual(s.target_index, 0)               # đang thu nose (index 0)
        # Thu nose trước để sang target chin.
        for _ in range(3):
            s.inject_frame(FrameState(points=pts(nasion=(320.0, 238.0),
                                                 nose=(320.0, 240.0))))
        self.assertEqual(s.target_index, 1)               # giờ đang cần chin
        big = BIG_BBOX   # bw=400, bh=350 → ry = max(40, .95*350) ≈ 332
        for _ in range(3):
            s.inject_frame(FrameState(points=pts(nasion=(320.0, 105.0),  # dy 135
                                                 chin=(320.0, 240.0)),
                                      bbox=big))
        self.assertIn("chin", s.captured)

    def test_face_ok_false_blocks_capture(self):
        """face_ok=False (mặt nhỏ/quá xa) → KHÔNG chụp dù mũi đúng tâm."""
        s, evs, clock = make_session()
        s.start("A")
        self._to_collect(s, clock)
        for _ in range(5):
            s.inject_frame(FrameState(points=pts(nasion=(320.0, 238.0),
                                                 nose=(320.0, 240.0)),
                                      face_ok=False))
        self.assertNotIn("nose", s.captured)
        self.assertEqual(s._hold_capture, 0)
        # bật lại face_ok → chụp được ngay.
        for _ in range(3):
            s.inject_frame(FrameState(points=pts(nasion=(320.0, 238.0),
                                                 nose=(320.0, 240.0)),
                                      face_ok=True))
        self.assertIn("nose", s.captured)

    def test_all_five_done(self):
        s, evs, clock = make_session()
        s.start("A")
        self._to_collect(s, clock)
        # Giả lập thu đủ 5 target bằng cách lái từng landmark vào tâm, với nasion
        # lệch đúng "pose" cho từng góc (được phép vì gate là elip co theo bbox mặt):
        big = BIG_BBOX  # bw=400 → rx=220, bh=350 → ry=332
        poses = {
            "nose":        (320.0, 238.0),   # chính diện: nasion sát tâm
            "chin":        (320.0, 110.0),   # ngước lên: nasion lệch trên sâu
            "forehead":    (320.0, 370.0),   # cúi xuống: nasion lệch dưới sâu
            "left_cheek":  (420.0, 240.0),   # xoay yaw trái: nasion lệch ngang
            "right_cheek": (220.0, 240.0),   # xoay yaw phải: nasion lệch ngang
        }
        import config
        for key, _, lm_name in config.ANGLES:
            for _ in range(3):
                s.inject_frame(FrameState(points=pts(nasion=poses[lm_name],
                                                     **{lm_name: (320.0, 240.0)}),
                                          bbox=big))
        self.assertEqual(len(s.captured), 5)
        self.assertEqual(s.state, CELEBRATE)
        self.assertEqual(evs[-1].kind, "DONE")

    def test_missing_landmark_mid_hold_resets(self):
        """Hồi quy bug #1a: target landmark biến mất giữa lúc giữ → _hold_capture
        về 0, KHÔNG cộng dồn qua khoảng trống. 3 frame chuẩn + 2 frame mất
        target + 3 frame chuẩn lại KHÔNG được chụp (bug cũ: 3+3=6 >= 5 → chụp
        đúng lúc 3 frame đầu sau gián đoạn) — phải đủ 5 liên tiếp SAU reset."""
        s, evs, clock = make_session(stable_capture=5)  # đủ cao để 3 frame chưa chụp
        s.start("A")
        self._to_collect(s, clock)
        self.assertEqual(s.target_index, 0)  # đang cần nose
        frame_ok = FrameState(points=pts(nasion=(320.0, 238.0),
                                         nose=(320.0, 240.0)))
        for _ in range(3):
            s.inject_frame(frame_ok)
        self.assertEqual(s._hold_capture, 3)
        self.assertNotIn("nose", s.captured)
        # Mất target 2 frame → reset hold + HOLD_FAIL đúng 1 lần (chỉ khi đang giữ).
        missing = FrameState(points=pts(nasion=(320.0, 238.0)))  # bỏ nose
        for _ in range(2):
            s.inject_frame(missing)
        self.assertEqual(s._hold_capture, 0)
        self.assertEqual(sum(1 for e in evs if e.kind == "HOLD_FAIL"), 1)
        # 3 frame chuẩn lại → hold chỉ tích từ lúc reset (không cộng dồn 3 cũ)
        # nên mới ở 3 → CHƯA chụp (bug cũ: 3+3=6 >= 5 → chụp ngay ở frame đầu).
        for _ in range(3):
            s.inject_frame(frame_ok)
        self.assertEqual(s._hold_capture, 3)
        self.assertNotIn("nose", s.captured)
        # Đủ 5 liên tiếp SAU gián đoạn → mới được chụp.
        for _ in range(2):
            s.inject_frame(frame_ok)
        self.assertEqual(s.captured, ["nose"])
        self.assertEqual(s._hold_capture, 0)

    def test_collect_timeout_recovery(self):
        """Hồi quy bug #1b: vào COLLECT nhưng không thỏa được target nào (vd điểm
        mốc index sai) → sau collect_timeout_secs thì về ALIGN_NASION + HOLD_FAIL,
        không treo vĩnh viễn."""
        s, evs, clock = make_session(collect_timeout_secs=15.0)
        s.start("A")
        self._to_collect(s, clock)
        self.assertEqual(s.state, COLLECT)
        # Chưa đủ timeout → vẫn ở COLLECT, chưa reset.
        clock.t += 14.0
        s.inject_frame(FrameState(points=pts(nasion=(320.0, 238.0))))  # mất nose
        self.assertEqual(s.state, COLLECT)
        # Quá timeout (15s) → về ALIGN_NASION + HOLD_FAIL.
        clock.t += 2.0
        s.inject_frame(FrameState(points=pts(nasion=(320.0, 238.0))))
        self.assertEqual(s.state, ALIGN_NASION)
        self.assertEqual(s.target_index, 0)
        self.assertEqual(s._hold_capture, 0)
        self.assertEqual(s._collect_entered_at, None)
        self.assertEqual(evs[-1].kind, "HOLD_FAIL")
        # sau khi hồi phục → chạy lại theo luồng từ đầu (align lên COUNTDOWN).
        for _ in range(3):
            s.inject_frame(FrameState(points=pts(nasion=(320.0, 240.0))))
        self.assertEqual(s.state, COUNTDOWN)

    def test_stable_capture_zero_captures_immediately(self):
        """Hồi quy bug #8: stable_capture=0 (chụp ngay) phải được cấu hình được
        (trước đây `stable_capture or config...` biến 0 → mặc định)."""
        s, evs, clock = make_session(stable_capture=0)
        s.start("A")
        self._to_collect(s, clock)
        # Chỉ 1 frame target đúng tâm → chụp ngay, hold reset về 0.
        s.inject_frame(FrameState(points=pts(nasion=(320.0, 238.0),
                                             nose=(320.0, 240.0))))
        self.assertEqual(s.captured, ["nose"])
        self.assertEqual(s._hold_capture, 0)


if __name__ == "__main__":
    unittest.main()