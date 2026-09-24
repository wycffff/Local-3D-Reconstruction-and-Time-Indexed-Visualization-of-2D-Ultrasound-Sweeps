"""Regression tests against the pinned upstream model; requires inference deps."""

import copy
from pathlib import Path
import sys
import unittest

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "external" / "DualTrack"))

from scripts.infer_one_sweep import load_dualtrack_2024_state
from src.models import get_model


CONFIG = {
    "name": "dualtrack_fusion_model",
    "local_encoder_cfg": {"name": "dualtrack_loc_enc_stg3_legacy"},
}


class CheckpointLoadingTests(unittest.TestCase):
    def setUp(self):
        self.model = get_model(**copy.deepcopy(CONFIG))
        self.state = self.model.state_dict()

    def legacy_state(self):
        self.state["global_encoder.fc.weight"] = torch.ones(12, 512)
        self.state["global_encoder.fc.bias"] = torch.ones(12)
        return self.state

    def test_legacy_weights_are_preserved_and_head_is_not_called(self):
        info = load_dualtrack_2024_state(self.model, self.legacy_state())
        self.assertEqual(info["checkpoint_weight_shape"], [12, 512])
        self.assertTrue(torch.equal(self.model.global_encoder.fc.weight, self.state["global_encoder.fc.weight"]))
        self.assertTrue(torch.equal(self.model.global_encoder.fc.bias, self.state["global_encoder.fc.bias"]))
        self.assertEqual(self.model.head.fc.out_features, 6)

        def forbid_head_call(*args):
            raise AssertionError("The auxiliary head must not participate in inference.")

        self.model.global_encoder.fc.register_forward_pre_hook(forbid_head_call)
        self.model.eval()
        with torch.inference_mode():
            features = self.model.global_encoder(torch.zeros(1, 2, 1, 224, 224), torch.tensor([[0, 1]]))
            prediction = self.model.head(features)
        self.assertEqual(tuple(prediction.shape), (1, 1, 6))
        self.assertTrue(torch.isfinite(prediction).all())

    def test_matching_state_needs_no_compatibility_change(self):
        self.assertIsNone(load_dualtrack_2024_state(self.model, self.state))

    def test_active_global_head_is_not_adapted(self):
        self.model.global_encoder.features_only = False
        with self.assertRaisesRegex(ValueError, "features-only"):
            load_dualtrack_2024_state(self.model, self.legacy_state())

    def test_unknown_global_head_shape_is_rejected(self):
        self.state["global_encoder.fc.weight"] = torch.zeros(13, 512)
        self.state["global_encoder.fc.bias"] = torch.zeros(13)
        with self.assertRaisesRegex(RuntimeError, "size mismatch"):
            load_dualtrack_2024_state(self.model, self.state)

    def test_final_pose_head_mismatch_is_rejected(self):
        self.legacy_state()
        self.state["head.fc.weight"] = torch.zeros(7, 512)
        with self.assertRaisesRegex(RuntimeError, "size mismatch for head.fc.weight"):
            load_dualtrack_2024_state(self.model, self.state)

    def test_missing_active_weight_is_rejected(self):
        self.legacy_state()
        del self.state["head.fc.weight"]
        with self.assertRaisesRegex(RuntimeError, "Missing key"):
            load_dualtrack_2024_state(self.model, self.state)

    def test_unexpected_weight_is_rejected(self):
        self.legacy_state()
        self.state["unknown.weight"] = torch.zeros(1)
        with self.assertRaisesRegex(RuntimeError, "Unexpected key"):
            load_dualtrack_2024_state(self.model, self.state)


if __name__ == "__main__":
    unittest.main()
