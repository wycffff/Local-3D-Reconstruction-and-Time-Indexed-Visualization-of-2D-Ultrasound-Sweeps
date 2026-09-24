"""Build an offline, time-indexed slice preview from one TUS-REC 2024 prediction."""

from __future__ import annotations

import argparse
import base64
from io import BytesIO
import json
from pathlib import Path


# Matches the pinned upstream src/submission/predictor.py pixel-to-image matrix.
# Pixel centers are zero-based; this maps the original 640x480 image into mm.
PIXEL_TO_IMAGE = [
    [0.22938919, 0, 0, -73.28984642],
    [0, 0.22097969, 0, -52.92463589],
    [0, 0, 1, 0],
    [0, 0, 0, 1],
]


def selected_indices(frame_count: int, max_frames: int):
    import numpy as np

    if frame_count < 2 or max_frames < 2:
        raise ValueError("At least two frames are required.")
    return np.unique(np.linspace(0, frame_count - 1, min(frame_count, max_frames)).round().astype(int))


def transform_pixels(pose, columns, rows):
    """Return HxWx3 points in frame-0 coordinates, with no tracking labels."""
    import numpy as np

    uu, vv = np.meshgrid(columns, rows)
    pixels = np.stack((uu, vv, np.zeros_like(uu), np.ones_like(uu)), axis=-1)
    return (pixels @ (np.asarray(pose) @ np.asarray(PIXEL_TO_IMAGE)).T)[..., :3]


def build_payload(result_dir: Path, input_path: Path | None, max_frames: int, pixel_step: int):
    import h5py
    import numpy as np
    from PIL import Image
    from inspect_result import inspect_result

    if not 2 <= max_frames <= 128 or not 4 <= pixel_step <= 32:
        raise ValueError("Use max_frames in [2,128] and pixel_step in [4,32].")
    report = inspect_result(result_dir)
    if not report["valid"]:
        raise ValueError(f"Result checks failed; inspect the arrays before previewing: {report['checks']}")
    metadata = json.loads((result_dir / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("model") != "DualTrack TUS-REC 2024":
        raise ValueError("This preview calibration is specific to DualTrack TUS-REC 2024.")
    input_path = (input_path or Path(metadata["input"])).resolve()
    poses = np.load(result_dir / "poses.npy", allow_pickle=False)
    indices = selected_indices(len(poses), max_frames)
    # Include the last pixel and retain ORIGINAL pixel coordinates after sampling.
    columns = np.unique(np.r_[np.arange(0, 640, pixel_step), 639]).astype(int)
    rows = np.unique(np.r_[np.arange(0, 480, pixel_step), 479]).astype(int)
    frames = []
    with h5py.File(input_path, "r") as handle:
        images = handle["frames"]  # Do not open tracking, tforms, or reference files.
        if images.shape != (len(poses), 480, 640) or images.dtype != np.dtype("uint8"):
            raise ValueError(f"Expected matching raw uint8 frames [{len(poses)},480,640], got {images.shape}/{images.dtype}.")
        for index in indices:
            image = images[int(index)]
            points = transform_pixels(poses[index], columns, rows)
            png = BytesIO()
            Image.fromarray(image).resize((320, 240), Image.Resampling.BOX).save(png, format="PNG")
            frames.append({
                "index": int(index),
                "points": points.round(4).reshape(-1, 3).tolist(),
                "intensity": image[np.ix_(rows, columns)].reshape(-1).tolist(),
                "png": "data:image/png;base64," + base64.b64encode(png.getvalue()).decode("ascii"),
            })
    centers = np.stack([transform_pixels(pose, [319.5], [239.5])[0, 0] for pose in poses])
    all_points = np.concatenate([np.asarray(frame["points"]) for frame in frames] + [centers])
    bounds = np.stack((all_points.min(axis=0), all_points.max(axis=0)))
    margin = np.maximum((bounds[1] - bounds[0]) * 0.08, 2)
    return {
        "source": input_path.name,
        "frame_count": len(poses),
        "frames": frames,
        "rows": len(rows),
        "columns": len(columns),
        "centers": centers.round(4).tolist(),
        "bounds": [(bounds[0] - margin).tolist(), (bounds[1] + margin).tolist()],
        "pixel_to_image": PIXEL_TO_IMAGE,
        "report": report,
        "pixel_step": pixel_step,
        "tracking_labels_used": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", type=Path, default=Path("results/first_sweep"))
    parser.add_argument("--input", type=Path, help="Only for relocating the SAME raw HDF5 used for inference; defaults to metadata. Same-shape files cannot be distinguished without a recorded hash.")
    parser.add_argument("--output", type=Path, help="Default: <result-dir>/preview.html; existing files are never overwritten.")
    parser.add_argument("--max-frames", type=int, default=64, help="Display sampling only; original predictions are untouched (2-128).")
    parser.add_argument("--pixel-step", type=int, default=8, help="Display sampling in original pixels (4-32).")
    args = parser.parse_args()
    result_dir = args.result_dir.resolve()
    output = (args.output or result_dir / "preview.html").resolve()
    if output.exists():
        raise FileExistsError(f"Preview exists: {output}. Choose a different --output.")
    try:
        from plotly.offline import get_plotlyjs
    except ImportError as exc:
        raise SystemExit("Install the viewer dependency: python -m pip install -r requirements-preview.txt") from exc
    payload = build_payload(result_dir, args.input, args.max_frames, args.pixel_step)
    template = Path(__file__).with_name("preview_template.html").read_text(encoding="utf-8")
    # Protect the script element even when an input filename contains HTML.
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    html = template.replace("__PLOTLY_JS__", get_plotlyjs(), 1).replace("__PAYLOAD__", encoded, 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(html)
    print(f"Checks passed. Displaying {len(payload['frames'])}/{payload['frame_count']} frames; inference results unchanged.")
    print(f"Saved offline preview: {output} ({output.stat().st_size / 2**20:.1f} MiB)")


if __name__ == "__main__":
    main()
