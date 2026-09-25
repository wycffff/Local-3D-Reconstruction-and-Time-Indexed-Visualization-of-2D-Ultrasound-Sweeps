# From a working model to a useful reconstruction

## Current result

One complete 318-frame TUS-REC 2024 sweep has completed DualTrack inference on a school RTX 2080 Ti. The first preview places original image samples using predicted poses. The maintainer has opened it, but reports opaque black areas and a result that still looks like stacked images. Geometric accuracy has not yet been measured.

These are separate questions:

| Question | How to answer it |
|---|---|
| Did the model execute and save consistent arrays? | The inference log and `inspect_result.py`. |
| Are the predicted slice locations close to the tracked reference? | Offline evaluation on the matching public scan. |
| Can the samples form a readable, continuous 3D view? | Voxel compounding, coverage inspection, and volume rendering. |

A clean-looking point cloud does not establish geometric accuracy. Removing black display pixels also does not turn a stack of planes into a fused volume.

## 1. Measure the current scan

Use the reference file already present in the downloaded validation archive:

```bash
python scripts/evaluate_result.py \
  --result-dir results/first_sweep \
  --reference data/tus_rec_2024_val/transfs/051/LH_Per_L_DtP.h5 \
  --output results/first_sweep/evaluation.json
```

This is an evaluation step after prediction. It reads the reference tracking, converts it into the same image coordinate system using the pinned official TUS-REC 2024 calibration, and compares image points after anchoring both trajectories at the first frame. It does not modify the saved prediction or fit a scale/trajectory alignment to make the error smaller. The inference and preview scripts remain independent of reference tracking.

The report distinguishes the official five-point convention from a sampled pixel-grid error. The default pixel stride is 4; use `--pixel-step 1` with a new output filename for a dense all-pixel check. A single scan and a sampled-grid result should not be treated as a reproduction of the paper's reported dataset average.

Look at the mean error, the final-frame error, the error over the sequence, and the stationary-pose baseline. Large or increasing errors motivate checking calibration, pairing, preprocessing, and then the predicted motion. A small error on one scan supports proceeding to fusion, but does not establish performance on a different device or anatomy. No arbitrary pass/fail accuracy threshold is imposed at this exploratory stage.

Sources: [official calibration conversion](https://github.com/ImFusionGmbH/DualTrack/blob/b904a3d41f4d1ca1ba1c192e2b213756650cfd15/scripts/data/convert_tus_rec_format_to_dualtrack_format.py), [official image-point metrics](https://github.com/ImFusionGmbH/DualTrack/blob/b904a3d41f4d1ca1ba1c192e2b213756650cfd15/src/dense_displacement_field.py), [DualTrack paper](https://arxiv.org/html/2509.09530v1).

## 2. Fuse the same predictions into a local volume

This is the next implementation milestone, not a feature of the current slice preview.

1. Define a small voxel grid around the predicted scan. Start with a configurable spacing around 1 mm for a manageable prototype, then examine whether finer spacing helps.
2. Map original pixels into the grid using the same physical calibration and predicted poses. Accumulate intensity and interpolation weights, then divide by the accumulated weights where coverage is nonzero.
3. Keep a coverage/count volume. Unobserved locations must remain distinguishable from measured dark tissue; avoid filling large unknown regions just to make a solid-looking object.
4. Inspect three orthogonal slices before tuning volume opacity. This makes holes, misalignment, and doubled structures easier to see than in a point cloud.
5. Add grayscale volume rendering with an adjustable opacity transfer function. Bright echoes and dark tissue should remain inspectable without permanently deleting low-intensity data.

Once the static volume is useful, retain a small number of cumulative reconstruction snapshots indexed by acquisition frame. A slider can then show the volume being built up. This represents sweep acquisition time; a single sweep does not recover independent, complete 3D anatomy at every instant.

This path reuses the running model and data. Gaussian splatting and a new learned reconstruction model are not required for this first fused-volume experiment.

## 3. Repeat on a few paired scans

After the current scan is interpretable, choose roughly 3–5 complete sweeps already in the public archive, including different sweep directions and lengths. Keep each prediction in a separate output directory and evaluate it against its matching reference file.

Record the scan identifier, frame count, runtime, GPU memory, point-displacement metrics, coverage, and visual failure modes. This small table is a more useful next decision point than one attractive screenshot. It also provides concrete material for a student engineering thesis: reproducibility, implementation choices, evaluation, and documented limitations.

Only after that check is it useful to try a different source video. Start with a source close to the model's input format and anatomy; arbitrary clinical video is outside the first milestone.

## Scope of the next deliverable

- A saved error report for the current 318-frame scan.
- A background-masked English preview, generated as a new HTML file.
- Next: a small predicted volume, its coverage map, and orthogonal/volume views.

The target is a reproducible local reconstruction prototype with an honest evaluation, not a guaranteed reconstruction of every ultrasound video.
