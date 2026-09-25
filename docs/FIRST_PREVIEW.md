# After the first successful sweep: inspect results and preview the geometry

The school workstation has completed CUDA inference on a full 318-frame scan and saved all three output files. Use those results below; there is no need to run the model again. The preview places original image slices and sampled pixels using the predicted poses. It does not perform voxel fusion or establish reconstruction accuracy.

The first preview runs, but its opaque black slice regions can obscure the accumulated points. The updated viewer adds display masking for those dark regions. This improves visibility without changing the predicted geometry.

## 1. Start the tunnel after boot

After starting the school Windows workstation and signing in, open Ubuntu:

```bash
"$HOME/.local/share/vscode-cli/code" tunnel --name insight-ultrasound
```

Keep this terminal running. In VS Code on your own computer, connect to `insight-ultrasound`, open `/home/yechuanwei/projects/ultrasound-sweeps`, and start a remote terminal. If the tunnel is already running, do not start another instance.

## 2. Update the code and inspect the saved result

```bash
cd ~/projects/ultrasound-sweeps
git pull --ff-only
source .venv/bin/activate
python scripts/inspect_result.py results/first_sweep
```

Expect `valid: true`, `frame_count: 318`, array shapes `[318,4,4]` and `[317,6]`, and all entries in `checks` set to true. The report also lists inference time, peak GPU memory, the GPU model, and the predicted trajectory's path length. Path length is not reconstruction error. Passing these checks shows numerical consistency, not geometric accuracy.

If inspection fails, retain the output. Do not modify the saved arrays merely to make the checks pass.

## 3. Generate a new offline HTML preview

Install the optional visualization dependency; this does not change PyTorch or CUDA:

```bash
python -m pip install -r requirements-preview.txt
python scripts/build_preview.py --result-dir results/first_sweep --output results/first_sweep/preview_v2.html
```

**Updating the source code does not update an existing HTML file.** The command generates `results/first_sweep/preview_v2.html`, leaving the original `preview.html` and all prediction arrays intact. Open the new file to use the updated interface.

The script locates the original HDF5 scan through `metadata.json` and reads only `frames` and the predicted results. It does not read reference tracking or `tforms`. Pixel calibration is specific to the 480×640 TUS-REC2024 data and must not be assumed valid for an arbitrary device or video.

By default, the display samples 64 of the 318 frames and approximately every eighth original pixel. The predictions for all 318 frames remain unchanged. The HTML contains its data, images, and plotting library, so it can be downloaded and opened offline in Chrome or Edge.

Existing HTML files are not overwritten. To use denser display sampling, save another file:

```bash
python scripts/build_preview.py --result-dir results/first_sweep --max-frames 96 --pixel-step 8 --output results/first_sweep/preview_dense.html
```

If the original scan has moved, supply `--input /new/absolute/path/to/the_same_scan.h5`. Do not substitute another scan with the same shape. Older predictions do not record an input hash, so shape checks alone cannot prove that the input is the same file.

## 4. Open the preview through remote VS Code

In a remote terminal at the school project directory, run:

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory results/first_sweep
```

Keep that terminal running. Open **Ports** in the bottom panel of VS Code. If it is hidden, use the command palette action `Ports: Focus on Ports View`. Select **Forward a Port**, enter `8000`, and click **Open in Browser** for that forwarded port. In the directory listing, open `preview_v2.html`.

Use the forwarding address supplied by VS Code; local port 8000 may not always be available. To stop the preview server, press `Ctrl+C` in its terminal. This does not delete the HTML or prediction files.

## 5. Inspect the display

- Rotate the 3D scene by dragging, and zoom with the wheel. Check whether the slices form a continuous spatial arrangement.
- Move the frame slider and check that the 2D image, current slice position, and accumulated points change together.
- Use playback and compare the current-slice, accumulated-history, and all-sampled-frames display modes.
- Keep **Hide dark background** enabled to hide dark pixels in the 3D slice. Its default cutoff is 5 on the 0–255 intensity scale. This is display masking, not anatomical segmentation; low-intensity tissue or fluid can also be hidden.
- Disable the current 3D slice when it obstructs the point cloud. The unchanged 2D image remains available for comparison.
- The point-cloud intensity threshold controls which echo pixels are shown. It does not identify tissue classes.

The timeline represents original frame order, not calibrated seconds. Accumulated points come from different acquisition frames. This display alone does not establish true tissue motion through time within a fully reconstructed 3D volume.

Development checks use synthetic HDF5 scans and known poses to verify coordinates, result-inspection failure paths, and viewer interactions. The school's actual reconstruction error still requires the reference-based checks described in [Next steps](NEXT_STEPS.md). Removing a black background cannot correct pose drift or turn stacked slices into a fused volume.
