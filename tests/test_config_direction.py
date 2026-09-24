"""Test cho việc đổi tên ANGLES sang hướng (direction-based) và R_ALIGN giảm 2/3.

Chạy: uv run python -m unittest tests.test_config_direction
"""
import unittest
import config


class TestAnglesDirectionNaming(unittest.TestCase):
    """ANGLES phải dùng key hướng thay vì tên giải phẫu."""

    def test_angles_keys_are_directions(self):
        keys = [key for key, _, _ in config.ANGLES]
        self.assertEqual(keys, ["center", "up", "down", "left", "right"],
                         "ANGLES keys phải là ['center','up','down','left','right']")

    def test_angles_landmark_names_match_keys(self):
        """landmark name trong ANGLES phải khớp với key (dùng làm dict key trong pts)."""
        for key, _, lm_name in config.ANGLES:
            self.assertEqual(key, lm_name,
                             f"key={key} phải bằng lm_name={lm_name}")

    def test_r_align_reduced_to_two_thirds(self):
        """R_ALIGN phải là 23 (34 * 2/3 ≈ 22.67, làm tròn 23)."""
        self.assertAlmostEqual(config.R_ALIGN, 23.0, places=1,
                               msg="R_ALIGN phải là 23 (2/3 của 34)")

    def test_angles_has_five_entries(self):
        self.assertEqual(len(config.ANGLES), 5)


if __name__ == "__main__":
    unittest.main()
