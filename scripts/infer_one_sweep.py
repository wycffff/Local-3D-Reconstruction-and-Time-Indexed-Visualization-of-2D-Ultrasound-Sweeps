"""Run the official DualTrack 2024 model on one complete TUS-REC image sequence.

Only the selected image dataset is read from HDF5. Tracking labels are not used.
A complete 318-frame TUS-REC sweep has run successfully on an RTX 2080 Ti.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="One TUS-REC 2024 HDF5 sweep.")
    parser.add_argument("--checkpoint", type=Path, required=True, help="Official dualtrack_final.pt.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for the three output files.")
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1] / "external" / "DualTrack",
        help="DualTrack checkout (default: external/DualTrack beside this project).",
    )
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda", help="CPU is supported but slow; default: cuda.")
    parser.add_argument(
        "--frames-key", choices=("frames", "images"), default="frames",
        help="Explicit HDF5 image key; raw TUS-REC uses frames (default).",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_dualtrack_2024_state(model, state) -> dict | None:
    """Restore the known, unused legacy head, then strictly load every tensor."""
    import torch

    compatibility = None
    weight = state.get("global_encoder.fc.weight")
    bias = state.get("global_encoder.fc.bias")
    if (
        isinstance(weight, torch.Tensor) and tuple(weight.shape) == (12, 512)
        and isinstance(bias, torch.Tensor) and tuple(bias.shape) == (12,)
    ):
        encoder = model.global_encoder
        fc = encoder.fc
        output_fc = model.head.fc
        if not (
            encoder.features_only is True
            and isinstance(fc, torch.nn.Linear)
            and (fc.in_features, fc.out_features) == (512, 6)
            and fc.bias is not None
            and isinstance(output_fc, torch.nn.Linear)
            and (output_fc.in_features, output_fc.out_features) == (512, 6)
        ):
            raise ValueError("Legacy global head compatibility requires a features-only encoder and the unchanged 6-DoF output head.")

        # Upstream global_encoder.py returns features before this fc is used.
        # The released 2024 checkpoint retains a 12-output auxiliary head, while
        # the current constructor creates 6. Restore its serialized shape rather
        # than filtering mismatches like the upstream non-strict loader does.
        encoder.fc = torch.nn.Linear(512, 12, device=fc.weight.device, dtype=fc.weight.dtype)
        compatibility = {
            "module": "global_encoder.fc",
            "original_weight_shape": [6, 512],
            "checkpoint_weight_shape": [12, 512],
            "original_bias_shape": [6],
            "checkpoint_bias_shape": [12],
            "reason": "Unused auxiliary head; global_encoder.features_only=True.",
            "final_output_dof": 6,
        }

    model.load_state_dict(state, strict=True)
    return compatibility


def main() -> None:
    args = parse_args()  # --help works before importing any optional dependency.
    args.repo = args.repo.resolve()
    args.input = args.input.resolve()
    args.checkpoint = args.checkpoint.resolve()
    args.output_dir = args.output_dir.resolve()
    config_path = args.repo / "configs" / "model" / "dualtrack.yaml"
    for path in (args.input, args.checkpoint, config_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    for name in ("poses.npy", "relative_motion.npy", "metadata.json"):
        if (args.output_dir / name).exists():
            raise FileExistsError(f"Output exists: {args.output_dir / name}. Choose a new output directory.")

    import h5py
    import numpy as np
    import torch
    import torchvision
    import transformers
    from omegaconf import OmegaConf
    from torchvision.transforms import v2

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable in this Python environment. Install CUDA-enabled PyTorch or use --device cpu.")
    device = torch.device(args.device)
    if device.type == "cpu":
        print("Running the complete sweep on CPU; this may be slow.", flush=True)

    # Access this dataset alone; never enumerate or load tracking/transform labels.
    with h5py.File(args.input, "r") as handle:
        if args.frames_key not in handle:
            raise KeyError(f"Missing HDF5 image dataset: {args.frames_key}")
        images = handle[args.frames_key]
        if not isinstance(images, h5py.Dataset):
            raise ValueError(f"{args.frames_key} is not an HDF5 dataset.")
        if images.ndim != 3 or images.shape[1:] != (480, 640):
            raise ValueError(f"Expected raw TUS-REC 2024 images [N,480,640], got {images.shape}.")
        if images.dtype != np.dtype("uint8"):
            raise ValueError(f"Expected uint8 images, got {images.dtype}.")
        frame_count = images.shape[0]
        if not 2 <= frame_count <= 1024:
            raise ValueError(
                f"Got {frame_count} frames; the official 2024 model supports at most 1024 positions. "
                "Use a complete supported sweep. This script does not truncate or subsample."
            )
        frames = images[:]

    sys.path.insert(0, str(args.repo))
    from src.models import get_model
    from src.utils.pose import get_global_and_relative_pred_trackings_from_vectors

    cfg = OmegaConf.to_container(OmegaConf.load(config_path), resolve=True)
    expected_cfg = {
        "name": "dualtrack_fusion_model",
        "local_encoder_cfg": {"name": "dualtrack_loc_enc_stg3_legacy"},
    }
    if cfg != expected_cfg:
        raise ValueError(f"Unexpected official 2024 model configuration: {cfg}")
    model = get_model(**copy.deepcopy(cfg))  # Keep the saved YAML config unchanged by upstream builders.
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    state = checkpoint["model"] if isinstance(checkpoint, dict) and "model" in checkpoint else checkpoint
    if not isinstance(state, dict) or not state or not all(isinstance(v, torch.Tensor) for v in state.values()):
        raise ValueError("Expected an official tensor state_dict, directly or under the 'model' key.")
    torch.nn.modules.utils.consume_prefix_in_state_dict_if_present(state, "_orig_mod.")
    checkpoint_compatibility = load_dualtrack_2024_state(model, state)
    if checkpoint_compatibility is not None:
        print("Restored unused legacy global encoder head (512 -> 12); final output remains 6-DoF.", flush=True)
    print(f"All checkpoint keys matched; predicting all {frame_count} frames on {device}.", flush=True)
    del checkpoint, state
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    model.to(device).eval()

    # Match configs/dualtrack_evaluation/dualtrack_final.yaml and the original
    # loader_factory/fusion_model_training.py, using torchvision v2 defaults.
    frames_tensor = torch.from_numpy(frames).unsqueeze(1).float().div_(255.0)
    global_images = v2.Normalize(mean=[0.5], std=[0.25])(v2.Resize((224, 224))(frames_tensor))
    local_images = v2.CenterCrop((256, 256))(frames_tensor).contiguous()
    del frames_tensor
    global_inputs = global_images.unsqueeze(0).to(device)
    local_inputs = local_images.unsqueeze(0).to(device)
    del global_images, local_images

    if device.type == "cuda":
        torch.cuda.synchronize()
    started = time.perf_counter()
    with torch.inference_mode(), torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
        prediction = model(global_inputs, local_inputs)
    if device.type == "cuda":
        torch.cuda.synchronize()
    inference_seconds = time.perf_counter() - started
    if prediction.shape != (1, frame_count - 1, 6):
        raise RuntimeError(f"Unexpected output shape: {tuple(prediction.shape)}")
    relative_motion = prediction[0].float().cpu().numpy()
    if not np.isfinite(relative_motion).all():
        raise RuntimeError("Model output contains NaN or infinity; no results saved.")
    poses, _ = get_global_and_relative_pred_trackings_from_vectors(relative_motion)
    if not np.isfinite(poses).all():
        raise RuntimeError("Accumulated poses contain NaN or infinity; no results saved.")

    try:
        revision = subprocess.check_output(
            ["git", "-C", str(args.repo), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    metadata = {
        "input": str(args.input),
        "hdf5_datasets_read": [args.frames_key],
        "tracking_labels_used": False,
        "input_shape": list(frames.shape),
        "input_dtype": str(frames.dtype),
        "full_sweep": True,
        "frame_stride": 1,
        "model": "DualTrack TUS-REC 2024",
        "model_config": cfg,
        "upstream_revision": revision,
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": sha256(args.checkpoint),
        "checkpoint_loaded_strictly": True,
        "checkpoint_compatibility": checkpoint_compatibility,
        "device": str(device),
        "device_name": torch.cuda.get_device_name() if device.type == "cuda" else "CPU",
        "torch_version": torch.__version__,
        "torchvision_version": torchvision.__version__,
        "transformers_version": transformers.__version__,
        "cuda_runtime": torch.version.cuda,
        "amp": device.type == "cuda",
        "inference_seconds": inference_seconds,
        "peak_cuda_allocated_gib": torch.cuda.max_memory_allocated() / 2**30 if device.type == "cuda" else None,
        "peak_cuda_reserved_gib": torch.cuda.max_memory_reserved() / 2**30 if device.type == "cuda" else None,
        "preprocessing": {
            "intensity": "uint8 / 255",
            "global": "resize 224x224 (bilinear, antialias); (x - 0.5) / 0.25",
            "local": "center crop 256x256; no further normalization",
        },
        "relative_motion": {
            "shape": list(relative_motion.shape),
            "columns": ["tx_mm", "ty_mm", "tz_mm", "rx_deg", "ry_deg", "rz_deg"],
            "rotation_convention": "scipy Rotation.from_euler('xyz', angles, degrees=True)",
            "mapping": "frame i+1 image coordinates to frame i image coordinates",
        },
        "poses": {
            "shape": list(poses.shape),
            "mapping": "frame i image coordinates to frame 0 image coordinates",
            "composition": "poses[0] = identity; poses[i+1] = poses[i] @ relative_transform[i]",
            "translation_units": "mm (model training coordinate convention)",
        },
        "note": "Inference output only; no accuracy evaluation or reconstructed volume is produced.",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.save(args.output_dir / "poses.npy", poses, allow_pickle=False)
    np.save(args.output_dir / "relative_motion.npy", relative_motion, allow_pickle=False)
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved poses.npy, relative_motion.npy and metadata.json to {args.output_dir}")


if __name__ == "__main__":
    main()
