"""List complete raw TUS-REC sweeps accepted by the first-run inference wrapper."""

import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--first", action="store_true", help="Print only the shortest matching complete sweep's absolute path")
    args = parser.parse_args()
    import h5py

    if not args.directory.is_dir():
        parser.error(f"Directory does not exist: {args.directory}")
    candidates = []
    for path in sorted(args.directory.rglob("*.h5")):
        try:
            with h5py.File(path, "r") as handle:
                if "frames" not in handle:
                    continue
                frames = handle["frames"]
                if not isinstance(frames, h5py.Dataset):
                    continue
                if (frames.ndim != 3 or frames.shape[1:] != (480, 640)
                        or not 2 <= frames.shape[0] <= 1024 or frames.dtype.name != "uint8"):
                    continue
                count = frames.shape[0]
            candidates.append((count, str(path.resolve())))
        except OSError as exc:
            print(f"Could not inspect {path}: {exc}", file=sys.stderr)
    if not candidates:
        print("No complete raw sweeps with uint8 frames [N,480,640], 2 <= N <= 1024, were found.", file=sys.stderr)
        return 1
    candidates.sort()
    if args.first:
        print(candidates[0][1])
    else:
        for count, path in candidates:
            print(f"{count:4d} frames  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
