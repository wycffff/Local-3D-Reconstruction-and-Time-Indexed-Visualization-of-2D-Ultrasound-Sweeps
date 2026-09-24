"""Read-only PyTorch/CUDA check. No extra packages needed to report missing torch."""

import argparse
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    report = {"python": sys.version.split()[0], "platform": platform.platform(),
              "cuda_ready": False, "packages": {}}
    for name in ("torch", "torchvision", "transformers", "timm", "h5py", "numpy"):
        try:
            report["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report["packages"][name] = None
    executable = shutil.which("nvidia-smi")
    if executable:
        result = subprocess.run(
            [executable, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=20, check=False,
        )
        report["nvidia_smi"] = {"returncode": result.returncode,
                                "output": result.stdout.strip(), "error": result.stderr.strip()}
    else:
        report["nvidia_smi"] = "Not found on PATH"
    try:
        import torch
        report["torch_cuda_runtime"] = torch.version.cuda
        report["cuda_available"] = torch.cuda.is_available()
        if report["cuda_available"]:
            report["gpus"] = [
                {"index": i, "name": torch.cuda.get_device_name(i),
                 "total_vram_gib": round(torch.cuda.get_device_properties(i).total_memory / 2**30, 2)}
                for i in range(torch.cuda.device_count())
            ]
            # Run a small operation: availability alone does not establish executable CUDA kernels.
            with torch.inference_mode():
                x = torch.ones((64, 64), device="cuda")
                actual = (x @ x)[0, 0].item()
            report["cuda_ready"] = actual == 64.0
            report["cuda_test_value"] = actual
    except Exception as exc:
        report["torch_error"] = f"{type(exc).__name__}: {exc}"
    report["scope"] = "CUDA environment check only; this does not run or validate DualTrack."
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    return 0 if report["cuda_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
