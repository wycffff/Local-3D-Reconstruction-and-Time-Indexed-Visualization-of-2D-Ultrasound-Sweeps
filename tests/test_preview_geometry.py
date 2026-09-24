import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_preview import selected_indices, transform_pixels


class PreviewGeometryTests(unittest.TestCase):
    def test_calibration_uses_original_zero_based_pixel_coordinates(self):
        points = transform_pixels(np.eye(4), [0, 8], [0, 8])
        np.testing.assert_allclose(points[0, 0], [-73.28984642, -52.92463589, 0])
        np.testing.assert_allclose(points[0, 1] - points[0, 0], [8 * .22938919, 0, 0])
        np.testing.assert_allclose(points[1, 0] - points[0, 0], [0, 8 * .22097969, 0])

    def test_pose_is_applied_after_pixel_calibration_without_inversion(self):
        pose = np.array([[0,-1,0,10],[1,0,0,20],[0,0,1,30],[0,0,0,1]], dtype=float)
        actual = transform_pixels(pose, [0], [0])[0, 0]
        np.testing.assert_allclose(actual, [52.92463589 + 10, -73.28984642 + 20, 30])

    def test_display_sampling_preserves_endpoints_and_original_indices(self):
        indices = selected_indices(318, 64)
        self.assertEqual(len(indices), 64)
        self.assertEqual(indices[0], 0)
        self.assertEqual(indices[-1], 317)
        self.assertTrue((np.diff(indices) > 0).all())
        np.testing.assert_array_equal(selected_indices(5, 64), np.arange(5))


if __name__ == "__main__":
    unittest.main()
