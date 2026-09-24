"""Check saved DualTrack inference results without loading images or tracking labels.

These checks establish numerical consistency, not reconstruction accuracy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def inspect_result(result_dir: Path | str) -> dict:
    """Return a JSON-serializable inspection; malformed files raise ValueError/OSError.

    ``valid`` is true only when all structural and numerical checks pass. No files
    are written. The returned trajectory distances describe the prediction in the
    model's millimetre convention; they are not an accuracy assessment.
    """
    import numpy as np
    from scipy.spatial.transform import Rotation

    result_dir = Path(result_dir)
    poses = np.load(result_dir / "poses.npy", allow_pickle=False)
    motion = np.load(result_dir / "relative_motion.npy", allow_pickle=False)
    metadata = json.loads((result_dir / "metadata.json").read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("metadata.json must contain an object.")
    for name, array in (("poses", poses), ("relative_motion", motion)):
        if not isinstance(array, np.ndarray) or array.dtype.kind not in "fiu":
            raise ValueError(f"{name}.npy must contain a real numeric array.")

    frame_count = int(poses.shape[0]) if poses.ndim else None
    pose_shape_ok = poses.ndim == 3 and poses.shape[1:] == (4, 4) and frame_count >= 2
    motion_shape_ok = (
        motion.ndim == 2 and motion.shape[1] == 6
        and frame_count is not None and motion.shape[0] == frame_count - 1
    )
    input_shape = metadata.get("input_shape")
    metadata_count_ok = (
        isinstance(input_shape, list) and len(input_shape) == 3
        and all(type(value) is int and value > 0 for value in input_shape)
        and input_shape[0] == frame_count
    )
    checks = {
        "poses_shape": bool(pose_shape_ok),
        "relative_motion_shape": bool(motion_shape_ok),
        "metadata_frame_count": bool(metadata_count_ok),
        "poses_finite": bool(np.isfinite(poses).all()),
        "relative_motion_finite": bool(np.isfinite(motion).all()),
        "homogeneous_last_row": False,
        "first_pose_identity": False,
        "rotations_orthogonal": False,
        "rotations_det_positive_one": False,
        "relative_motion_matches_poses": False,
    }
    errors = {
        "max_rotation_orthogonality_error": None,
        "max_rotation_determinant_error": None,
        "max_pose_composition_error": None,
    }
    trajectory = {
        "path_length_mm": None,
        "endpoint_displacement_mm": None,
        "max_step_mm": None,
        "note": "Predicted image-origin path in model coordinates; not an accuracy measurement.",
    }
    if pose_shape_ok and checks["poses_finite"]:
        values = poses.astype(np.float64)
        rotations = values[:, :3, :3]
        orthogonality_error = float(np.max(np.abs(rotations.transpose(0, 2, 1) @ rotations - np.eye(3))))
        determinant_error = float(np.max(np.abs(np.linalg.det(rotations) - 1.0)))
        errors["max_rotation_orthogonality_error"] = orthogonality_error
        errors["max_rotation_determinant_error"] = determinant_error
        checks["homogeneous_last_row"] = bool(np.allclose(values[:, 3, :], [0, 0, 0, 1], rtol=0, atol=1e-6))
        checks["first_pose_identity"] = bool(np.allclose(values[0], np.eye(4), rtol=0, atol=1e-6))
        # Upstream accumulates up to 1024 transforms in float32; allow rounding.
        checks["rotations_orthogonal"] = orthogonality_error <= 1e-4
        checks["rotations_det_positive_one"] = determinant_error <= 1e-4
        origins = values[:, :3, 3]
        step_lengths = np.linalg.norm(np.diff(origins, axis=0), axis=1)
        trajectory["path_length_mm"] = float(step_lengths.sum())
        trajectory["endpoint_displacement_mm"] = float(np.linalg.norm(origins[-1] - origins[0]))
        trajectory["max_step_mm"] = float(step_lengths.max())

        if motion_shape_ok and checks["relative_motion_finite"]:
            # Match pinned upstream get_global_and_relative_pred_trackings_from_vectors:
            # T maps frame i+1 into frame i, composed on the right, stored float32.
            expected = np.empty(poses.shape, dtype=np.float32)
            expected[0] = np.eye(4)
            for index, vector in enumerate(motion):
                transform = np.eye(4)
                transform[:3, :3] = Rotation.from_euler("xyz", vector[3:], degrees=True).as_matrix()
                transform[:3, 3] = vector[:3]
                expected[index + 1] = expected[index] @ transform
            if np.isfinite(expected).all():
                errors["max_pose_composition_error"] = float(np.max(np.abs(values - expected)))
                checks["relative_motion_matches_poses"] = bool(np.allclose(values, expected, rtol=1e-5, atol=1e-5))

    runtime = {
        key: metadata.get(key)
        for key in (
            "device", "device_name", "inference_seconds", "peak_cuda_allocated_gib",
            "peak_cuda_reserved_gib", "torch_version", "cuda_runtime", "amp",
        )
    }
    report = {
        "valid": all(checks.values()),
        "frame_count": frame_count,
        "shapes": {"poses": list(poses.shape), "relative_motion": list(motion.shape)},
        "checks": checks,
        "runtime": runtime,
        "trajectory": trajectory,
        "numerical_errors": errors,
        "scope": "Numerical consistency only; no tracking labels read and no accuracy evaluation.",
    }
    # Fail clearly on malformed metadata rather than emitting non-standard NaN JSON.
    try:
        json.dumps(report, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Inspection contains a non-finite value or invalid runtime metadata.") from exc
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_dir", type=Path, nargs="?", default=Path("results/first_sweep"))
    args = parser.parse_args()  # --help works without numpy or scipy installed.
    try:
        report = inspect_result(args.result_dir)
    except (OSError, ValueError, ImportError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
