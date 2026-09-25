"""Calibration and offline metrics, using independent known-motion references."""

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_result import (
    displacement_metrics,
    evaluate_result,
    reference_poses_from_tforms,
    tus_rec_2024_calibration,
    validate_rigid_sequence,
)


def identities(count=3):
    return np.repeat(np.eye(4)[None], count, axis=0)


class ReferenceGeometryTests(unittest.TestCase):
    def test_conversion_matches_pinned_official_converter_without_importing_pipeline(self):
        source_path = ROOT / "external/DualTrack/scripts/data/convert_tus_rec_format_to_dualtrack_format.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        converter_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TUSRecToDualTrackConverter")
        # Execute only the dependency-free class. Do not import pandas or its CLI.
        namespace = {"np": np}
        exec(compile(ast.Module(body=[converter_node], type_ignores=[]), str(source_path), "exec"), namespace)
        converter = namespace["TUSRecToDualTrackConverter"].from_hardcoded_tus_rec_2024_calibration_settings()
        calibration, pixel_matrix = tus_rec_2024_calibration()
        np.testing.assert_array_equal(pixel_matrix, converter.pixel_to_image_in_dualtrack_coords)
        np.testing.assert_allclose(calibration, converter.convert_tracking_sequence(np.eye(4)), rtol=0, atol=1e-12)
        raw = identities()
        raw[0, :3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
        raw[0, :3, 3] = [11, 20, -13]
        raw[1, :3, :3] = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]
        raw[1, :3, 3] = [-10, 22, 9]
        raw[2, :3, :3] = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]
        raw[2, :3, 3] = [14, 11, 40]
        official_world = converter.convert_tracking_sequence(raw)
        expected = np.linalg.inv(official_world[0]) @ official_world
        actual = reference_poses_from_tforms(raw)
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-10)
        np.testing.assert_allclose(actual[0], np.eye(4), rtol=0, atol=1e-12)
        self.assertFalse(np.allclose(actual, np.linalg.inv(raw[0]) @ raw))
        # A new tracker world origin/orientation must cancel during anchoring.
        world_change = np.array([[0, 1, 0, 30], [0, 0, 1, -90], [1, 0, 0, 70], [0, 0, 0, 1]])
        np.testing.assert_allclose(reference_poses_from_tforms(world_change @ raw), actual, rtol=0, atol=1e-10)

    def test_perfect_prediction_and_known_translation(self):
        truth = identities()
        truth[1:, 0, 3] = [7, 14]
        perfect = displacement_metrics(truth, truth)
        self.assertEqual(perfect["global_pixel_displacement_error_mm"]["mean"], 0)
        self.assertEqual(perfect["five_point_global_error_mm"]["mean"], 0)
        self.assertEqual(perfect["stationary_identity_baseline_mm"]["mean"], 10.5)
        prediction = truth.copy()
        prediction[1:, :3, 3] += [3, 4, 0]
        actual = displacement_metrics(prediction, truth)
        np.testing.assert_allclose(actual["global_pixel_displacement_error_mm"]["per_frame_mean"], [5, 5])
        self.assertEqual(actual["five_point_global_error_mm"]["mean"], 5)
        self.assertEqual(actual["centered_image_origin_error_mm"]["last_frame"], 5)
        self.assertEqual(actual["sampling"]["evaluated_frame_indices"], [1, 2])
        self.assertEqual(actual["sampling"]["pixel_count_per_frame"], 19200)

    def test_official_five_points_include_width_and_height_and_differ_from_dense(self):
        truth = identities(2)
        prediction = truth.copy()
        prediction[1, :3, :3] = np.diag([-1, -1, 1])
        actual = displacement_metrics(prediction, truth, 1)
        points = np.array([[0, 0], [640, 0], [0, 480], [640, 480], [320, 240]])
        # A 180-degree in-plane rotation displaces each point twice its radius.
        physical_xy = points * [.22938919, .22097969] + [-73.28984642, -52.92463589]
        expected = (2 * np.linalg.norm(physical_xy, axis=1)).mean()
        self.assertAlmostEqual(actual["five_point_global_error_mm"]["mean"], expected)
        self.assertEqual(actual["five_point_global_error_mm"]["points_px"], points.tolist())
        self.assertNotAlmostEqual(actual["global_pixel_displacement_error_mm"]["mean"], expected)
        self.assertEqual(actual["sampling"]["pixel_count_per_frame"], 307200)
        self.assertEqual(actual["sampling"]["mode"], "dense")
        self.assertAlmostEqual(actual["rotation_error_degrees"]["mean"], 180)

    def test_stationary_zero_baseline_uses_null_improvement(self):
        report = displacement_metrics(identities(), identities())
        self.assertIsNone(report["stationary_identity_baseline_mm"]["prediction_improvement_percent"])
        json.dumps(report, allow_nan=False)

    def test_invalid_shape_numeric_values_and_nonrigid_transforms_are_rejected(self):
        for invalid in [np.eye(4), identities(1), identities().astype(complex)]:
            with self.subTest(shape=invalid.shape, dtype=invalid.dtype), self.assertRaises(ValueError):
                validate_rigid_sequence(invalid, "Test")
        for row, column, value in [(1, 1, np.nan), (3, 0, 1), (0, 0, -1), (0, 0, 2)]:
            invalid = identities()
            invalid[1, row, column] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_rigid_sequence(invalid, "Test")
        with self.assertRaisesRegex(ValueError, "frame count"):
            displacement_metrics(identities(), identities(2))
        unanchored = identities()
        unanchored[0, 0, 3] = 5
        with self.assertRaisesRegex(ValueError, "anchored"):
            displacement_metrics(unanchored, identities())
        for step in [0, -1, 33, 1.5, True]:
            with self.subTest(step=step), self.assertRaisesRegex(ValueError, "pixel_step"):
                displacement_metrics(identities(), identities(), step)


class OfflineEvaluationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.result_dir = self.root / "results"
        self.result_dir.mkdir()
        self.reference = self.root / "transfs/051/test.h5"
        self.reference.parent.mkdir(parents=True)
        self.poses = identities(2).astype(np.float32)
        self.poses[1, :3, 3] = [3, 4, 0]
        np.save(self.result_dir / "poses.npy", self.poses)
        np.save(self.result_dir / "relative_motion.npy", np.array([[3, 4, 0, 0, 0, 0]], dtype=np.float32))
        self.metadata = {
            "model": "DualTrack TUS-REC 2024", "input": "/relocated/data/frames/051/test.h5",
            "input_shape": [2, 480, 640], "input_dtype": "uint8",
            "full_sweep": True, "frame_stride": 1, "tracking_labels_used": False,
        }
        self.write_metadata()
        calibration, _ = tus_rec_2024_calibration()
        world = np.array([[0, -1, 0, 10], [1, 0, 0, 30], [0, 0, 1, -3], [0, 0, 0, 1]])
        self.tforms = world @ self.poses @ np.linalg.inv(calibration)
        self.write_reference(self.tforms)

    def write_metadata(self):
        (self.result_dir / "metadata.json").write_text(json.dumps(self.metadata), encoding="utf-8")

    def write_reference(self, values):
        with h5py.File(self.reference, "w") as handle:
            handle["tforms"] = values

    def test_complete_offline_report_without_reading_images_or_changing_predictions(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.result_dir.iterdir()}
        report = evaluate_result(self.result_dir, self.reference)
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.result_dir.iterdir()}
        self.assertEqual(before, after)
        self.assertAlmostEqual(report["global_pixel_displacement_error_mm"]["mean"], 0)
        self.assertAlmostEqual(report["stationary_identity_baseline_mm"]["mean"], 5)
        self.assertEqual(report["reference_hdf5_datasets_read"], ["tforms"])
        self.assertTrue(report["pairing"]["subject_directory_matches"])
        self.assertEqual(report["frame_count"], 2)

    def test_wrong_subject_filename_or_model_is_rejected(self):
        for replacement in ["/frames/052/test.h5", "/frames/051/other.h5"]:
            self.metadata["input"] = replacement
            self.write_metadata()
            with self.subTest(path=replacement), self.assertRaisesRegex(ValueError, "does not match"):
                evaluate_result(self.result_dir, self.reference)
        self.metadata["input"] = "/frames/051/test.h5"
        self.metadata["model"] = "DualTrack TUS-REC 2025"
        self.write_metadata()
        with self.assertRaisesRegex(ValueError, "only DualTrack TUS-REC 2024"):
            evaluate_result(self.result_dir, self.reference)

    def test_wrong_label_shape_and_invalid_prediction_are_rejected(self):
        self.write_reference(identities(3))
        with self.assertRaisesRegex(ValueError, "tforms shape"):
            evaluate_result(self.result_dir, self.reference)
        self.write_reference(self.tforms)
        self.poses[1, 0, 3] += 2
        np.save(self.result_dir / "poses.npy", self.poses)
        with self.assertRaisesRegex(ValueError, "failed numerical inspection"):
            evaluate_result(self.result_dir, self.reference)

    def test_cli_writes_json_and_refuses_to_overwrite(self):
        output = self.result_dir / "evaluation.json"
        command = [sys.executable, str(ROOT / "scripts/evaluate_result.py"), "--result-dir", str(self.result_dir), "--reference", str(self.reference), "--output", str(output)]
        completed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Official five-point convention", completed.stdout)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["sampling"]["pixel_step"], 4)
        again = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("Output exists", again.stderr)


if __name__ == "__main__":
    unittest.main()
