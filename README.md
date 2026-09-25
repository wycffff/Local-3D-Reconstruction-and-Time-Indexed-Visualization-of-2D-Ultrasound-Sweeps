# Local 3D Reconstruction and Time-Indexed Visualization of 2D Ultrasound Sweeps

A research prototype for local 3D reconstruction and time-indexed visualization from 2D ultrasound sweeps.

**Status: one complete 318-frame scan has run successfully on an RTX 2080 Ti using CUDA, and its interactive 3D preview has been opened. The initial display shows stacked slices with dark regions obscuring the view. Reconstruction accuracy has not yet been measured.**

The first milestone is to run the authors' pretrained model on its matching TUS-REC2024 data and obtain predicted frame poses. The next steps are to improve the display, compare predictions with the dataset's reference tracking, and fuse slices into a local volume before trying other ultrasound videos.

## Start here

- **INSIGHT workstation with two RTX 2080 Ti GPUs, Windows and WSL2:** [Remote tunnel, project synchronization and setup](docs/INSIGHT_SETUP.md).
- Existing Linux GPU environment: [First model run](FIRST_RUN.md).
- Saved prediction files: [Result checks and interactive 3D preview](docs/FIRST_PREVIEW.md).
- After the first preview: [Accuracy evaluation and next experiments](docs/NEXT_STEPS.md).

```bash
git clone --recurse-submodules https://github.com/wycffff/Local-3D-Reconstruction-and-Time-Indexed-Visualization-of-2D-Ultrasound-Sweeps.git ultrasound-sweeps
cd ultrasound-sweeps
```

## Repository contents

| Path | Purpose |
|---|---|
| `external/DualTrack` | Official upstream code, pinned as a Git submodule with its original license |
| `requirements-inference.txt` | Dependencies for the first inference experiment |
| `scripts/check_gpu.py` | Inspect Python/CUDA and run a small GPU computation |
| `scripts/list_sweeps.py` | List HDF5 scans supported by the initial inference script |
| `scripts/infer_one_sweep.py` | Read images, load all checkpoint parameters strictly, and save predicted poses |
| `scripts/inspect_result.py` | Check array values, rotations, and motion integration consistency |
| `scripts/build_preview.py` | Build an offline 3D HTML preview from original images and predicted poses |
| `scripts/evaluate_result.py` | Compare saved predictions with reference tracking from the matching dataset |
| `requirements-preview.txt` | Optional visualization dependency, installed separately from inference dependencies |

`data/`, `checkpoints/`, `results/`, local environments, and reference videos are excluded from Git. GitHub synchronizes code; the VS Code tunnel connects to the school workstation, where the code runs.

The inference script uses one GPU. The two 2080 Ti cards do not automatically provide a combined 22 GB of VRAM.

Project documentation, code, command output, and the preview interface use English. Discussion and assistance can remain in Chinese.

## Validation status and sources

The school terminal confirmed successful CUDA inference and saved outputs for all 318 frames of `LH_Per_L_DtP.h5`. The initial preview also runs, but a working renderer does not establish geometric accuracy. Dark-background masking affects only the display; reference-based evaluation is the next check.

The inference script handles a legacy auxiliary-head shape difference in the official checkpoint. Local CPU validation confirmed that all 854 checkpoint entries load strictly and match the supplied values, and a short synthetic sequence passed a full forward run. Result inspection and preview geometry have also been tested on synthetic inputs. No measured reconstruction error for the school scan is reported yet.

The DualTrack submodule is pinned to `b904a3d41f4d1ca1ba1c192e2b213756650cfd15`. The model, upstream code, and dataset retain their respective authors' terms. This repository does not redistribute weights or data.

- [DualTrack](https://github.com/ImFusionGmbH/DualTrack)
- [DualTrack paper](https://arxiv.org/html/2509.09530v2)
- [TUS-REC2024 validation dataset](https://zenodo.org/records/12979481)
