# First run: predict one ultrasound sweep with DualTrack 2024

For tunnel setup, cloning, and testing on the school's Windows + WSL2 workstation with two RTX 2080 Ti cards, follow the [INSIGHT setup guide](docs/INSIGHT_SETUP.md).

The first goal is to load the authors' checkpoint and process one complete scan from the matching dataset, producing predicted frame-to-frame motion and a 3D trajectory.

Status as of 2026-09-25: after fixing compatibility with the checkpoint's legacy auxiliary head, the school GPU completed inference on a full 318-frame scan and saved all three output files. The interactive preview also runs. Continue with [result inspection and the updated preview](docs/FIRST_PREVIEW.md), then [accuracy evaluation](docs/NEXT_STEPS.md). Geometric accuracy remains unmeasured.

## Prepared files

- `external/DualTrack`: unmodified official source at commit `b904a3d41f4d1ca1ba1c192e2b213756650cfd15`.
- `scripts/check_gpu.py`: checks Python, PyTorch, CUDA, and a small matrix operation.
- `scripts/infer_one_sweep.py`: reads only the raw HDF5 `frames`, without reading `tforms`; strictly checks checkpoint compatibility and saves predicted arrays.
- `scripts/list_sweeps.py`: lists complete scans supported by the initial script.
- `requirements-inference.txt`: inference dependencies. The first school scan has succeeded; the exact runtime versions are recorded in its `metadata.json`.

## Hardware and runtime

Use an available Linux x86-64 machine with an NVIDIA GPU. Start with Python 3.11, preferably 12–16 GB of VRAM, 16–32 GB of RAM, and about 25 GB of free disk space. These are planning allowances, not minimum requirements published by the authors. The school's 11 GB RTX 2080 Ti has already completed the 318-frame test. On a Windows NVIDIA workstation, use Ubuntu under WSL2 for the first experiment.

The paper reports less than 7 GB of inference VRAM for 546 frames on an RTX Quadro 6000. Requirements vary with sequence length, runtime, and preprocessing. Neither multiple GPUs nor training from scratch is needed for the first run.

The NVIDIA driver and a CUDA-enabled PyTorch build are the essential components. Prebuilt PyTorch packages normally include the required CUDA runtime libraries. This workflow does not explicitly compile custom CUDA extensions, so a separate full CUDA Toolkit installation is usually unnecessary. On a school cluster, run checks and inference inside an allocated GPU job, not on a login node.

## Prepare an isolated environment on Linux

Copy or clone the project to the target machine and enter its directory. If `external/DualTrack` was not included, initialize the pinned submodule:

```bash
git submodule update --init --recursive
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Choose an officially supported PyTorch CUDA wheel for the GPU and driver. The cu126 combination below is the version used for the first school test; it does not imply compatibility with every machine:

```bash
python -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r requirements-inference.txt
python -m pip check
python scripts/check_gpu.py --output results/environment.json
```

The report should include `cuda_ready: true`. This confirms a basic CUDA operation, not successful model inference. The upstream requirements include many training and notebook dependencies and list both Pillow and Pillow_SIMD. This project installs the dependencies needed for the initial inference path separately. Record the actual runtime versions if they change.

## Obtain the official checkpoint and a matching scan

Download the checkpoint from the authors' source:

```bash
mkdir -p checkpoints data results
curl -fL --retry 3 https://downloads.imfusion.com/DualTrack/dualtrack_final.pt -o checkpoints/dualtrack_final.pt
```

Use the [public TUS-REC2024 validation dataset](https://zenodo.org/records/12979481), approximately 4.8 GB as a ZIP. The full training dataset is not needed. Retain the dataset's terms and citation information. The [INSIGHT guide](docs/INSIGHT_SETUP.md#8-remote-ubuntu-download-the-checkpoint-and-validation-data) includes a resumable download command.

After extraction, choose an original scan `.h5` whose `frames` dataset is a uint8 grayscale sequence shaped `[N,H,W]`. For the first run, use a complete scan with at most 1024 frames. Do not arbitrarily subsample or truncate a scan and treat it as the authors' original evaluation sequence.

```bash
python scripts/infer_one_sweep.py --input /absolute/path/to/one_scan.h5 --checkpoint checkpoints/dualtrack_final.pt --output-dir results/first_sweep
```

Replace `/absolute/path/to/one_scan.h5` with the actual scan path. Use the 2024 checkpoint, not the 2025 fine-tuned version.

Expected outputs are `poses.npy`, `relative_motion.npy`, and `metadata.json`. Inference does not read reference poses. Displaying slices in millimeters also requires the dataset's image calibration; pose arrays alone are not a reconstructed volume. Checkpoint loading, a successful forward pass, numerical consistency, and geometric accuracy are separate checks.

If CUDA is unavailable, check the target environment. If checkpoint keys do not match, retain the full error rather than allowing silent partial loading. If GPU memory runs out, record the GPU, frame count, and error, then select a shorter complete scan or a GPU with more available memory.

## Sources

- [Official DualTrack repository and checkpoint table](https://github.com/ImFusionGmbH/DualTrack)
- [DualTrack paper v2: experiments and inference resources](https://arxiv.org/html/2509.09530v2)
- [Official PyTorch 2.7.1 installation combinations](https://pytorch.org/get-started/previous-versions/#v271)
- [PyTorch forum: runtime libraries and drivers](https://discuss.pytorch.org/t/how-do-i-get-started-with-cuda-and-pytorch/223816)

The immediate sequence is: inspect predictions and the 3D preview, measure error against the matching reference tracking, then test local volume fusion and additional ultrasound videos. Keep each experiment small and preserve its outputs.
