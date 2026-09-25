"""Evaluate an existing TUS-REC 2024 prediction against paired tracking labels.

This is an offline evaluation only. Labels never enter inference, and prediction
files are never changed. The default regular pixel grid is sampled, so this is
not a reproduction of the paper's complete evaluation protocol.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import sys


UPSTREAM_REVISION = "b904a3d41f4d1ca1ba1c192e2b213756650cfd15"
CALIBRATION_SOURCE = (
    "https://github.com/ImFusionGmbH/DualTrack/blob/" + UPSTREAM_REVISION
    + "/scripts/data/convert_tus_rec_format_to_dualtrack_format.py"
)


def tus_rec_2024_calibration():
    """Return centered-image-to-tool and pixel-to-centered-image matrices.

    Copy the released converter's full-precision calibration and its separately
    rounded pixel matrix exactly; these two translations must not be conflated.
    """
    import numpy as np

    image_to_tool = np.asarray([
        [0.231064671309448, -0.21805203504134, 0.948189025293473, -70.7413291931152],
        [-0.190847036221471, -0.965787272832032, -0.175591436013112, -80.6505661010742],
        [0.954036962825936, -0.140386087807861, -0.264773903381482, -46.1766223907471],
        [0, 0, 0, 1],
    ], dtype=np.float64)
    spacing = (0.229389190673828, 0.220979690551758)
    tus_rec_image_to_centered_image = np.eye(4)
    tus_rec_image_to_centered_image[0, 3] = (-640 / 2 - 0.5) * spacing[0]
    tus_rec_image_to_centered_image[1, 3] = (-480 / 2 - 0.5) * spacing[1]
    centered_image_to_tool = image_to_tool @ np.linalg.inv(tus_rec_image_to_centered_image)
    pixel_to_image = np.asarray([
        [0.22938919, 0, 0, -73.28984642],
        [0, 0.22097969, 0, -52.92463589],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ], dtype=np.float64)
    return centered_image_to_tool, pixel_to_image


def validate_rigid_sequence(values, name: str, frame_count: int | None = None):
    """Validate SE(3) matrices without repairing or projecting their rotations."""
    import numpy as np

    values = np.asarray(values)
    if values.dtype.kind not in "fiu":
        raise ValueError(f"{name} must contain real numeric values.")
    if values.ndim != 3 or values.shape[1:] != (4, 4) or len(values) < 2:
        raise ValueError(f"{name} must have shape [N,4,4], N >= 2; got {values.shape}.")
    if frame_count is not None and len(values) != frame_count:
        raise ValueError(f"{name} frame count {len(values)} does not match prediction {frame_count}.")
    values = values.astype(np.float64)
    if not np.isfinite(values).all():
        raise ValueError(f"{name} contains NaN or infinity.")
    if not np.allclose(values[:, 3], [0, 0, 0, 1], rtol=0, atol=1e-6):
        raise ValueError(f"{name} has invalid homogeneous last rows.")
    rotations = values[:, :3, :3]
    if not np.allclose(rotations.transpose(0, 2, 1) @ rotations, np.eye(3), rtol=0, atol=1e-4):
        raise ValueError(f"{name} contains non-orthogonal rotations.")
    if not np.allclose(np.linalg.det(rotations), 1, rtol=0, atol=1e-4):
        raise ValueError(f"{name} contains rotations whose determinant is not +1.")
    return values


def reference_poses_from_tforms(tforms):
    """Convert raw tool-to-world labels, then anchor them at the first image.

    The pinned converter computes W_i = raw_i @ image_to_tool @
    centered_image_to_tus_rec_image. Prediction-compatible poses are inv(W_0) @
    W_i, not inv(raw_0) @ raw_i and not the inverse of the tracking labels.
    """
    import numpy as np

    raw = validate_rigid_sequence(tforms, "Reference tforms")
    centered_image_to_tool, _ = tus_rec_2024_calibration()
    image_to_world = raw @ centered_image_to_tool
    poses = np.linalg.inv(image_to_world[0]) @ image_to_world
    return validate_rigid_sequence(poses, "Converted reference poses", len(raw))


def displacement_metrics(predicted_poses, reference_poses, pixel_step: int = 4) -> dict:
    """Measure per-pixel global position error with first-frame anchoring only.

    For original zero-based pixels p=(u,v,0,1), error is
    ||(P_i C p - R_i C p)[:3]||_2, i=1..N-1. Subtracting the common first-frame
    position gives the equivalent displacement-field error. No fitting is used.
    """
    import numpy as np

    if type(pixel_step) is not int or not 1 <= pixel_step <= 32:
        raise ValueError("pixel_step must be an integer in [1,32].")
    predicted = validate_rigid_sequence(predicted_poses, "Predicted poses")
    reference = validate_rigid_sequence(reference_poses, "Reference poses", len(predicted))
    for name, sequence in (("Predicted", predicted), ("Reference", reference)):
        if not np.allclose(sequence[0], np.eye(4), rtol=0, atol=1e-6):
            raise ValueError(f"{name} poses must already be anchored at an identity first frame.")
    _, pixel_to_image = tus_rec_2024_calibration()
    columns = np.arange(0, 640, pixel_step)
    rows = np.arange(0, 480, pixel_step)
    uu, vv = np.meshgrid(columns, rows)
    pixels = np.stack((uu.ravel(), vv.ravel(), np.zeros(uu.size), np.ones(uu.size)))
    image_points = pixel_to_image @ pixels
    # Stream one frame at a time; even the dense option never builds N full DDFs.
    means = []
    baseline_means = []
    five_point_pixels = np.asarray([
        [0, 0, 0, 1], [640, 0, 0, 1], [0, 480, 0, 1],
        [640, 480, 0, 1], [320, 240, 0, 1],
    ], dtype=np.float64).T
    five_points = pixel_to_image @ five_point_pixels
    five_point_means = []
    for prediction, truth in zip(predicted[1:], reference[1:]):
        differences = ((prediction - truth) @ image_points)[:3]
        means.append(float(np.linalg.norm(differences, axis=0).mean()))
        five_point_differences = ((prediction - truth) @ five_points)[:3]
        five_point_means.append(float(np.linalg.norm(five_point_differences, axis=0).mean()))
        stationary_differences = ((np.eye(4) - truth) @ image_points)[:3]
        baseline_means.append(float(np.linalg.norm(stationary_differences, axis=0).mean()))
    mean_error = float(np.mean(means))
    baseline_error = float(np.mean(baseline_means))
    # Compare the origin and orientation of each centered image coordinate frame.
    origin_errors = np.linalg.norm(predicted[1:, :3, 3] - reference[1:, :3, 3], axis=1)
    relative_rotations = reference[1:, :3, :3].transpose(0, 2, 1) @ predicted[1:, :3, :3]
    cosines = (np.trace(relative_rotations, axis1=1, axis2=2) - 1) / 2
    angles = np.rad2deg(np.arccos(np.clip(cosines, -1, 1)))
    return {
        "global_pixel_displacement_error_mm": {
            "mean": mean_error,
            "max_frame_mean": float(np.max(means)),
            "last_frame_mean": means[-1],
            "per_frame_mean": means,
        },
        "five_point_global_error_mm": {
            "mean": float(np.mean(five_point_means)),
            "last_frame_mean": five_point_means[-1],
            "per_frame_mean": five_point_means,
            "points_px": five_point_pixels[:2].T.astype(int).tolist(),
            "note": "Pinned upstream five-point convention uses width=640 and height=480, not last pixel indices. One sweep only; not the paper's multi-sweep aggregate.",
        },
        "stationary_identity_baseline_mm": {
            "mean": baseline_error,
            "last_frame_mean": baseline_means[-1],
            "per_frame_mean": baseline_means,
            "prediction_improvement_percent": (
                100 * (1 - mean_error / baseline_error) if baseline_error > 1e-12 else None
            ),
            "note": "Identity for every frame; evaluated on the same pixels and frames. Negative improvement means worse than stationary.",
        },
        "centered_image_origin_error_mm": {
            "mean": float(origin_errors.mean()), "last_frame": float(origin_errors[-1]),
        },
        "rotation_error_degrees": {"mean": float(angles.mean()), "last_frame": float(angles[-1])},
        "sampling": {
            "mode": "dense" if pixel_step == 1 else "regular_sampled_grid",
            "pixel_step": pixel_step,
            "image_width": 640,
            "image_height": 480,
            "pixel_count_per_frame": int(uu.size),
            "column_count": len(columns), "row_count": len(rows),
            "grid_definition": "u=range(0,640,pixel_step), v=range(0,480,pixel_step); original zero-based pixel centers",
            "evaluated_frame_indices": list(range(1, len(predicted))),
            "first_frame_excluded": True,
        },
    }


def validate_pairing(metadata: dict, reference_path: Path) -> dict:
    """Require matching subject/name where recorded; hashes were not saved."""
    raw_input = metadata.get("input")
    if not isinstance(raw_input, str) or not raw_input:
        raise ValueError("Metadata must identify the image input to pair the reference.")
    image_path = PurePosixPath(raw_input.replace("\\", "/"))
    if image_path.name != reference_path.name:
        raise ValueError(f"Reference filename {reference_path.name!r} does not match image input {image_path.name!r}.")
    subject = image_path.parent.name
    if subject and subject != reference_path.parent.name:
        raise ValueError(f"Reference subject {reference_path.parent.name!r} does not match image input parent {subject!r}.")
    return {
        "filename_matches": True,
        "subject_directory_matches": True if subject else None,
        "subject": subject or None,
        "limitation": "Filename, subject directory and frame count are checked; no recorded image/reference hash establishes file identity.",
    }


def evaluate_result(result_dir: Path | str, reference_path: Path | str, pixel_step: int = 4) -> dict:
    """Return a report without writing files, reading images, or changing poses."""
    import h5py
    import numpy as np
    if __package__:
        from .inspect_result import inspect_result
    else:
        from inspect_result import inspect_result

    result_dir = Path(result_dir).resolve()
    reference_path = Path(reference_path).resolve()
    inspection = inspect_result(result_dir)
    if not inspection["valid"]:
        raise ValueError(f"Prediction failed numerical inspection: {inspection['checks']}")
    metadata = json.loads((result_dir / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("model") != "DualTrack TUS-REC 2024":
        raise ValueError("The hardcoded calibration supports only DualTrack TUS-REC 2024 results.")
    if metadata.get("input_shape") != [inspection["frame_count"], 480, 640] or metadata.get("input_dtype") != "uint8":
        raise ValueError("Evaluation requires the complete raw uint8 TUS-REC 2024 image shape [N,480,640].")
    if metadata.get("full_sweep") is not True or metadata.get("frame_stride") != 1:
        raise ValueError("Evaluation requires a complete, unstrided sweep with one prediction per raw frame.")
    if metadata.get("tracking_labels_used") is not False:
        raise ValueError("Metadata must confirm that inference did not use tracking labels.")
    pairing = validate_pairing(metadata, reference_path)
    poses = np.load(result_dir / "poses.npy", allow_pickle=False)
    with h5py.File(reference_path, "r") as handle:
        if "tforms" not in handle or not isinstance(handle["tforms"], h5py.Dataset):
            raise ValueError("Reference file must contain raw TUS-REC tool-to-world matrices in dataset 'tforms'.")
        dataset = handle["tforms"]
        if dataset.shape != (len(poses), 4, 4):
            raise ValueError(f"Reference tforms shape {dataset.shape} does not match ({len(poses)},4,4).")
        raw_tforms = validate_rigid_sequence(dataset[:], "Reference tforms", len(poses))
    reference_poses = reference_poses_from_tforms(raw_tforms)
    metrics = displacement_metrics(poses, reference_poses, pixel_step)
    report = {
        "scope": "Offline tracking-reference evaluation of saved predictions; no labels are used in inference or substituted into the preview.",
        "result_dir": str(result_dir), "reference": str(reference_path),
        "reference_hdf5_datasets_read": ["tforms"],
        "frame_count": len(poses), "pairing": pairing,
        "calibration": {
            "dataset": "TUS-REC 2024", "source": CALIBRATION_SOURCE,
            "pixel_to_image": tus_rec_2024_calibration()[1].tolist(),
            "conversion": "W_i = raw_tforms_i @ centered_image_to_tool; R_i = inverse(W_0) @ W_i",
        },
        "alignment": "First-frame anchoring only; no best-fit rigid, scale, or similarity alignment.",
        "metric_definition": "Mean over frames i=1..N-1 and sampled original pixels p of norm((P_i @ C @ p - R_i @ C @ p)[:3]), in mm.",
        "protocol_note": "One-sweep diagnostic, not a reproduction of the paper's full evaluation protocol. Pixel sampling is explicit; use --pixel-step 1 for the dense grid.",
        **metrics,
    }
    json.dumps(report, allow_nan=False)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", type=Path, default=Path("results/first_sweep"))
    parser.add_argument("--reference", type=Path, required=True, help="Paired raw transfs/<subject>/<scan>.h5 containing 'tforms'.")
    parser.add_argument("--output", type=Path, help="Default: <result-dir>/evaluation.json; existing files are never overwritten.")
    parser.add_argument("--pixel-step", type=int, default=4, help="Regular pixel-grid step (1-32); 1 evaluates all 307200 pixels per frame.")
    args = parser.parse_args()
    output = (args.output or args.result_dir / "evaluation.json").resolve()
    try:
        if output.exists():
            raise FileExistsError(f"Output exists: {output}. Choose a different --output.")
        report = evaluate_result(args.result_dir, args.reference, args.pixel_step)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    except (OSError, ValueError, KeyError, ImportError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1
    sampling = report["sampling"]
    metric = report["global_pixel_displacement_error_mm"]
    baseline = report["stationary_identity_baseline_mm"]
    print(f"Evaluated {report['frame_count'] - 1} frames, {sampling['pixel_count_per_frame']} pixels/frame ({sampling['mode']}, step={sampling['pixel_step']}).")
    print(f"Global pixel displacement error: {metric['mean']:.3f} mm mean; {metric['last_frame_mean']:.3f} mm last frame.")
    print(f"Official five-point convention: {report['five_point_global_error_mm']['mean']:.3f} mm mean (this sweep only).")
    print(f"Stationary baseline: {baseline['mean']:.3f} mm mean. No best-fit alignment applied.")
    print(f"Saved offline evaluation: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
