"""Numerical-result checks using known motions, without model or label access."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.inspect_result import inspect_result


class ResultInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        # A 90-degree turn makes right- versus left-composition distinguishable.
        self.motion = np.array([[1, 0, 0, 0, 0, 90], [2, 0, 0, 0, 0, 0]], dtype=np.float32)
        self.poses = np.repeat(np.eye(4)[None, :, :], 3, axis=0).astype(np.float32)
        self.poses[1:, :3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
        self.poses[1, :3, 3] = [1, 0, 0]
        self.poses[2, :3, 3] = [1, 2, 0]
        # No checkpoint_compatibility field: older results remain supported.
        self.metadata = {"input_shape": [3, 480, 640], "device_name": "synthetic fixture", "inference_seconds": 0.1}

    def save(self):
        np.save(self.directory / "poses.npy", self.poses, allow_pickle=False)
        np.save(self.directory / "relative_motion.npy", self.motion, allow_pickle=False)
        (self.directory / "metadata.json").write_text(json.dumps(self.metadata), encoding="utf-8")

    def inspect(self):
        self.save()
        return inspect_result(self.directory)

    def test_known_turn_and_translation_with_older_metadata(self):
        report = self.inspect()
        self.assertTrue(report["valid"], report["checks"])
        self.assertEqual(report["frame_count"], 3)
        self.assertAlmostEqual(report["trajectory"]["path_length_mm"], 3.0)
        self.assertAlmostEqual(report["trajectory"]["endpoint_displacement_mm"], np.sqrt(5))
        self.assertEqual(report["runtime"]["device_name"], "synthetic fixture")
        json.dumps(report, allow_nan=False)

    def test_wrong_composition_order_fails_despite_valid_rigid_poses(self):
        self.poses[2, :3, 3] = [3, 0, 0]
        report = self.inspect()
        self.assertFalse(report["valid"])
        self.assertFalse(report["checks"]["relative_motion_matches_poses"])
        self.assertTrue(report["checks"]["rotations_orthogonal"])

    def test_noncommuting_euler_angles_use_extrinsic_xyz_degrees(self):
        self.motion[0, 3:] = [90, 90, 0]
        # R_y(90) @ R_x(90), independently specified, distinguishes Euler order.
        self.poses[1:, :3, :3] = [[0, 1, 0], [0, 0, -1], [-1, 0, 0]]
        self.poses[2, :3, 3] = [1, 0, -2]
        self.assertTrue(self.inspect()["valid"])

    def test_reflection_is_rejected_even_though_orthogonal(self):
        self.poses[2, :3, :3] = np.diag([-1, 1, 1])
        report = self.inspect()
        self.assertTrue(report["checks"]["rotations_orthogonal"])
        self.assertFalse(report["checks"]["rotations_det_positive_one"])

    def test_scaled_rotation_bad_origin_and_last_row_are_detected(self):
        self.poses[2, :3, :3] *= 1.1
        self.poses[0, 0, 3] = 1
        self.poses[2, 3, 0] = 0.5
        report = self.inspect()
        for check in ("rotations_orthogonal", "first_pose_identity", "homogeneous_last_row"):
            self.assertFalse(report["checks"][check], check)

    def test_nan_motion_is_reported_without_nan_json(self):
        self.motion[0, 0] = np.nan
        report = self.inspect()
        self.assertFalse(report["checks"]["relative_motion_finite"])
        self.assertFalse(report["checks"]["relative_motion_matches_poses"])
        json.dumps(report, allow_nan=False)

    def test_mismatching_shapes_and_metadata_do_not_pass(self):
        self.motion = self.motion[:1]
        self.metadata["input_shape"][0] = 4
        report = self.inspect()
        self.assertFalse(report["checks"]["relative_motion_shape"])
        self.assertFalse(report["checks"]["metadata_frame_count"])
        self.poses = np.zeros((3, 3, 3))
        self.assertFalse(self.inspect()["checks"]["poses_shape"])

    def test_cli_rejects_invalid_result_and_help_needs_no_dependencies(self):
        self.motion[0, 0] = np.inf
        self.save()
        failed = subprocess.run([sys.executable, str(ROOT / "scripts/inspect_result.py"), str(self.directory)], capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertFalse(json.loads(failed.stdout)["valid"])
        help_result = subprocess.run([sys.executable, "-S", str(ROOT / "scripts/inspect_result.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)


if __name__ == "__main__":
    unittest.main()
