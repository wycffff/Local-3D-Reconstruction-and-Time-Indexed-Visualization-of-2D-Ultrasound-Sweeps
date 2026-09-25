# INSIGHT dual RTX 2080 Ti: connection, synchronization, and first inference

This guide assumes that the school workstation runs Windows with Ubuntu under WSL2 and has two RTX 2080 Ti GPUs. Each step identifies the computer and terminal to use. For a native Linux workstation, skip the WSL-specific checks.

Status as of 2026-09-25: a complete 318-frame scan has finished CUDA inference with strict checkpoint loading, saved all three output files, and opened in the interactive preview. Continue with [result inspection and the updated 3D preview](FIRST_PREVIEW.md), then [accuracy evaluation](NEXT_STEPS.md). **Each 2080 Ti has 11 GB of VRAM; two cards do not automatically provide 22 GB to one inference run.** Test other sequences according to their length and available memory.

## Quick start after each boot

The current setup starts the tunnel manually. After booting the school workstation and signing in to Windows, open Ubuntu and run:

```bash
"$HOME/.local/share/vscode-cli/code" tunnel --name insight-ultrasound
```

Keep that terminal running. GitHub sign-in usually does not need to be repeated. On your own computer, use VS Code's `Remote Tunnels: Connect to Tunnel` action to connect to `insight-ultrasound`, open `/home/yechuanwei/projects/ultrasound-sweeps`, and create a remote terminal:

```bash
cd ~/projects/ultrasound-sweeps
source .venv/bin/activate
nvidia-smi
```

Do not start another tunnel if its process is still running. Activate `.venv` in each new Python terminal; dependencies and data do not need to be installed or downloaded again. When providing instructions for starting or resuming this project, include the tunnel command above.

VS Code supports `code tunnel service install`, but installing a service inside WSL does not by itself start Ubuntu when Windows boots. Automatic startup needs separate configuration. Continue with the manual process for now. [Official tunnel documentation](https://code.visualstudio.com/docs/remote/tunnels)

## Where the project lives and whether to move it

On 2026-09-24, the user confirmed approximately 105 GB of free disk space and chose to keep the current location until more space is needed.

The project is at `/home/yechuanwei/projects/ultrasound-sweeps` inside WSL. Run the following in Ubuntu on the school workstation to open the same directory in Windows File Explorer:

```bash
cd ~/projects/ultrasound-sweeps
explorer.exe .
```

Alternatively, enter `\\wsl.localhost\` in the school's Windows File Explorer address bar, select the actual Ubuntu distribution, and open `home\yechuanwei\projects\ultrasound-sweeps`. This is the same directory, not another copy. WSL2 Linux files are normally stored in an `ext4.vhdx` virtual disk. Its Windows location depends on how the distribution was installed; the Linux path alone does not establish that it is on drive C. See [WSL file access](https://learn.microsoft.com/en-us/windows/wsl/filesystems) and [WSL disk space](https://learn.microsoft.com/en-us/windows/wsl/disk-space).

Check project size and free space on the Windows drives:

```bash
du -sh ~/projects/ultrasound-sweeps
df -h /mnt/c /mnt/d /mnt/e
```

The `du` result excludes Python installations, download caches, and other Ubuntu files outside the project. In `df`, inspect the `Avail` column. With sufficient space, continue testing without moving the project. If the dataset grows, moving the whole WSL distribution to D or E can preserve the existing `/home/...` paths and virtual environment. Do not drag `ext4.vhdx` manually. Moving a project with its `.venv` directly to `/mnt/d` is also not recommended; Linux tools generally work faster inside the WSL filesystem. Plan any migration separately, after stopping inference and the tunnel, using the actual distribution name, WSL version, and destination drive.

## 0. What the two connections do

| Connection | Purpose |
|---|---|
| Your VS Code → tunnel → school WSL | Edit school files and run Python/GPU tasks on the school workstation |
| Your Git ↔ GitHub ↔ school Git | Synchronize committed code and documentation with explicit push/pull operations |

Saving in the remote VS Code window writes directly to the school machine. It does not update a separate checkout on your own computer. To update that checkout, commit and push from the school machine, then pull locally.

Set the school workstation's sleep behavior while plugged in to **Never**, and keep the tunnel terminal running. No background service is configured initially. The screen can be locked, but shutdown, hibernation, signing out of Windows, closing the tunnel process, or running `wsl --shutdown` may interrupt the connection.

## 1. School workstation / Windows PowerShell: check WSL and GPUs

```powershell
wsl --list --verbose
nvidia-smi
```

Expected: the Ubuntu distribution shows VERSION `2`, and `nvidia-smi` lists two 2080 Ti cards. Its CUDA Version field indicates driver compatibility, not an installed full CUDA Toolkit.

If only docker-desktop is listed, install an Ubuntu distribution for development. In administrator PowerShell, run `wsl --install -d Ubuntu-24.04`, then follow the restart and initial Linux user setup prompts.

If Ubuntu shows VERSION 1, convert it using its actual name from the list, for example:

```powershell
wsl --set-version Ubuntu-24.04 2
```

Use `wsl --update` if an update is needed. Perform conversion or updates during setup, not while inference is running.

Open Ubuntu from the Windows Start menu. Alternatively, run `wsl -d Ubuntu-24.04`, replacing the distribution name with the actual name in the list.

## 2. School workstation / Ubuntu: check GPU access from Linux

```bash
uname -r
uname -m
printf '%s\n' "$WSL_DISTRO_NAME"
nvidia-smi
```

Expected: the kernel name includes `microsoft` or `WSL2`, the architecture is `x86_64`, the distribution is Ubuntu, and the GPUs are visible.

If the only error is `nvidia-smi: command not found`, try:

```bash
/usr/lib/wsl/lib/nvidia-smi
```

If GPU access works in Windows but fails in WSL, check WSL2, WSL updates, and the Windows NVIDIA driver. **Do not install a Linux NVIDIA display driver inside WSL.** WSL uses the Windows driver. Inference with this project's prebuilt PyTorch package also normally does not require a separate full CUDA Toolkit. [NVIDIA WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)

## 3. School workstation / Ubuntu: start the Linux VS Code tunnel

```bash
sudo apt-get update
sudo apt-get install -y curl ca-certificates tar git unzip
mkdir -p "$HOME/.local/share/vscode-cli"
cd "$HOME/.local/share/vscode-cli"
curl -fL 'https://update.code.visualstudio.com/latest/cli-linux-x64/stable' -o vscode-cli.tar.gz
tar -xzf vscode-cli.tar.gz
./code --version
```

Expected: the VS Code CLI version is printed. This explicitly installs the Linux CLI. A bare `code` command in WSL may invoke the Windows VS Code launcher and connect to a different environment.

Sign in:

```bash
"$HOME/.local/share/vscode-cli/code" tunnel user login --provider github
```

Open the URL shown in the terminal and enter its device code to sign in to GitHub as `wycffff`. Enter the code yourself on the sign-in page. Tunnel authentication is separate from the Git push authentication configured later.

Start the tunnel:

```bash
"$HOME/.local/share/vscode-cli/code" tunnel --name insight-ultrasound
```

On the first run, read and accept the server license when prompted. A successful connection should print a URL such as `https://vscode.dev/tunnel/insight-ultrasound`. **It is normal for the process to stay running without returning to a command prompt. Keep this terminal open.**

## 4. Your computer / VS Code: connect to the school workstation

1. First open the URL printed by the tunnel in a browser and sign in with the same GitHub account, `wycffff`. If the remote editor opens, the tunnel works.
2. In desktop VS Code on your own computer, press `Ctrl+Shift+X` and install Microsoft's **Remote - Tunnels** extension, ID `ms-vscode.remote-server`.
3. Press `Ctrl+Shift+P` and run `Remote Tunnels: Connect to Tunnel`.
4. Sign in with the same GitHub account and select `insight-ultrasound`.
5. In the remote window, select **Terminal → New Terminal**.

Run these commands in that remote terminal:

```bash
uname -r
printf '%s\n' "$WSL_DISTRO_NAME"
pwd
nvidia-smi
```

Expected: the school's Linux/WSL environment and 2080 Ti GPUs, rather than your own computer's PowerShell. If the remote terminal runs Windows, check that the tunnel was started in Ubuntu using the full path to the Linux CLI.

All subsequent Ubuntu commands can run in this remote terminal. VS Code tunnels do not require separate SSH configuration or router port forwarding. [Microsoft Remote Tunnels documentation](https://code.visualstudio.com/docs/remote/tunnels)

## 5. Remote Ubuntu: clone the project and pinned upstream source

```bash
mkdir -p "$HOME/projects"
cd "$HOME/projects"
git clone --recurse-submodules https://github.com/wycffff/Local-3D-Reconstruction-and-Time-Indexed-Visualization-of-2D-Ultrasound-Sweeps.git ultrasound-sweeps
cd ultrasound-sweeps
git status
git submodule status
```

Expected: a clean working tree and a DualTrack submodule commit beginning with `b904a3d`. If the submodule status starts with `-`, run `git submodule update --init --recursive`.

Keep the project in `/home/<linux-user>/projects/ultrasound-sweeps`, within the WSL Linux filesystem.

In VS Code, select **File → Open Folder** and open that path. Run `pwd` first if needed to copy the exact path. New terminals should then open in the project directory; there is no need to run `code .` in the remote terminal.

## 6. Remote Ubuntu: create an isolated Python 3.11 environment

Use uv to install a standalone Python version, avoiding differences between Ubuntu's default Python versions without changing the system interpreter.

```bash
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/ultrasound-uv-install.sh
sh /tmp/ultrasound-uv-install.sh
"$HOME/.local/bin/uv" python install 3.11
cd "$HOME/projects/ultrasound-sweeps"
"$HOME/.local/bin/uv" venv --python 3.11 --seed .venv
source .venv/bin/activate
python --version
which python
```

Expected: Python 3.11.x and a path ending in this project's `.venv/bin/python`. Activate the environment with `source .venv/bin/activate` in each new terminal.

Install the PyTorch versions used by the upstream project:

```bash
python -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r requirements-inference.txt
python -m pip check
```

This first-run setup uses cu126 and requires a compatible Windows NVIDIA driver. The school workstation has passed both the CUDA check and the first inference run with this procedure; actual runtime versions are recorded in the result's `metadata.json`. If another machine reports an outdated driver, address its Windows driver or choose an officially supported CUDA wheel for that driver. Do not install arbitrary Linux display drivers in WSL. [PyTorch installation matrix](https://pytorch.org/get-started/previous-versions/#v271)

## 7. Remote Ubuntu: test a GPU computation

```bash
python scripts/check_gpu.py --output results/environment.json
```

Expected: `cuda_available: true`, `cuda_ready: true`, `cuda_test_value: 64.0`, and a list of GPUs.

Check that model dependencies can be imported:

```bash
PYTHONPATH=external/DualTrack python -c "from src.models import get_model; print('DualTrack imports OK')"
```

This checks dependencies only. The following steps test the real checkpoint and real ultrasound images.

## 8. Remote Ubuntu: download the checkpoint and validation data

```bash
mkdir -p checkpoints data results
curl -fL --retry 3 https://downloads.imfusion.com/DualTrack/dualtrack_final.pt -o checkpoints/dualtrack_final.pt
```

After the checkpoint download finishes, run the entire block below separately. If the validation download is interrupted, keep the partial ZIP and rerun this block to resume; the checkpoint does not need to be downloaded again. Each failed attempt restarts `curl -C -` using the latest file size. If all attempts fail, extraction does not proceed.

```bash
(
  for attempt in {1..10}; do
    if curl -fL --retry 3 --connect-timeout 30 -C - \
      'https://zenodo.org/records/12979481/files/Freehand_US_data_val.zip?download=1' \
      -o data/Freehand_US_data_val.zip; then
      exit 0
    fi
    if [ "$attempt" -lt 10 ]; then
      printf 'Download interrupted; resume in 15 seconds (%s/10).\n' "$attempt"
      sleep 15
    fi
  done
  printf 'Download failed. Keep the partial ZIP and retry later.\n' >&2
  exit 1
) &&
unzip -tq data/Freehand_US_data_val.zip &&
unzip -n data/Freehand_US_data_val.zip -d data/tus_rec_2024_val &&
python scripts/list_sweeps.py data/tus_rec_2024_val
```

The checkpoint is approximately 408 MB and the validation ZIP is approximately 4.8 GB. Allow about 25 GB for installation and extraction. If the download is slow or returns HTTP 429, preserve the partial file and resume later rather than repeatedly starting parallel downloads. A manual download from the [official dataset page](https://zenodo.org/records/12979481) is another option.

`curl: (18)` means the transfer was incomplete. In that situation, `End-of-central-directory signature not found` is a subsequent error caused by attempting to extract an incomplete ZIP. The ordinary `--retry` behavior does not cover error 18; the outer loop above starts a fresh resume attempt. Use `-o` to write the file rather than replacing it with `>` or `>>`. After downloading, `unzip -tq` checks integrity; extraction and scan listing run only if that check passes. [curl documentation](https://curl.se/docs/manpage.html#--continue-at)

Expected: entries such as `N frames /absolute/path/to/scan.h5`. The script selects complete original scans with the required image shape and 2–1024 frames, skipping landmark files. This limit belongs to the initial inference script, not to every model version or inference strategy.

## 9. Remote Ubuntu: run the first real inference on one GPU

Check current GPU use:

```bash
nvidia-smi
```

Choose a GPU with sufficient free memory. The example below uses GPU 0. The scan selector chooses the shortest supported complete scan to reduce memory pressure while preserving the original sequence:

```bash
US_SWEEP="$(python scripts/list_sweeps.py data/tus_rec_2024_val --first)"
printf '%s\n' "$US_SWEEP"
CUDA_VISIBLE_DEVICES=0 python scripts/infer_one_sweep.py --input "$US_SWEEP" --checkpoint checkpoints/dualtrack_final.pt --output-dir results/first_sweep
```

To use the other GPU, change `CUDA_VISIBLE_DEVICES=0` to `1`. Inside the process, it is still called logical device `cuda:0`; this is the expected remapping.

Expected: `All checkpoint keys matched`, followed by confirmation that three files were saved. Inference reads images only, without reference poses.

The official 2024 checkpoint contains a legacy 12-output `global_encoder.fc` auxiliary head, while the current upstream constructor creates a 6-output head. Fusion inference uses `features_only=True` and does not execute that auxiliary head. For this known shape difference, the script restores the matching auxiliary head and still loads every parameter with `strict=True`. The change is recorded under `checkpoint_compatibility` in `metadata.json`. The actual pose-output head remains 6-dimensional; other missing or mismatched entries are not ignored. If an older script reports a `[12,512]` versus `[6,512]` mismatch for this layer, run `git pull --ff-only` in the project directory and repeat the inference command. Dependencies and the checkpoint do not need to be downloaded again.

Development validation on Windows / Python 3.12 / PyTorch 2.7.1 CPU used the real official checkpoint to verify that all 854 entries loaded strictly and matched their supplied values. A full forward pass on 32 synthetic frames produced finite output with shape `(1,31,6)`. The school workstation subsequently completed the real 318-frame CUDA run. With inference dependencies installed, run `python -m unittest discover -s tests -v` for the available regression checks.

```bash
python -c "import numpy as np; p=np.load('results/first_sweep/poses.npy'); print('shape:', p.shape); print('finite:', np.isfinite(p).all()); print('first pose:', p[0])"
```

Expected: `shape` is `(frame_count, 4, 4)`, `finite` is True, and the first pose is the identity matrix. `relative_motion.npy` contains adjacent-frame motion. `metadata.json` records the checkpoint checksum, versions, timing, and other run details.

**This confirms that prediction finished; it does not establish acceptable geometric accuracy.** Continue with [the preview](FIRST_PREVIEW.md) and [reference-based evaluation](NEXT_STEPS.md). Preserve the first result. For a new run, use another directory such as `--output-dir results/second_sweep`; existing outputs are never overwritten.

## 10. Routine code synchronization

Before pushing from the school workstation for the first time, configure Git identity and authentication in remote Ubuntu:

```bash
git config user.name "Yechuan Wei"
git config user.email "157529217+wycffff@users.noreply.github.com"
sudo apt-get install -y gh
gh auth login
gh auth setup-git
```

Choose GitHub.com, HTTPS, and browser sign-in. Cloning and pulling this public repository do not require authentication; this setup enables pushing.

Before editing:

```bash
git status
git pull --ff-only
git submodule update --init --recursive
```

If you have uncommitted edits, commit your work first rather than using a forced reset. After editing, inspect and commit the intended changes. The following example covers scripts and documentation; stage only the paths you intend to synchronize:

```bash
git diff
git add scripts docs README.md FIRST_RUN.md requirements-inference.txt
git diff --cached --stat
git commit -m "Update first-run experiment"
git push
```

To update the checkout on your own computer, open its project folder in local PowerShell and run `git pull --ff-only` followed by `git submodule update --init --recursive`. Running these commands in the remote window updates the school checkout, not your local copy.

Git synchronizes committed content, not live edits in both directions. If `pull --ff-only` cannot fast-forward, retain the error and resolve the branch divergence rather than using `push --force`. The virtual environment, raw data, checkpoints, and results are ignored and remain separate on each computer. Small result files can be downloaded through the remote VS Code Explorer's **Download** action.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Tunnel is missing | Same GitHub account at both ends; school tunnel process, workstation, and network are online |
| Remote terminal is PowerShell | The school tunnel may use the Windows CLI; start the Linux CLI from Ubuntu using its full path |
| Windows sees the GPU but WSL does not | WSL version/updates and the Windows NVIDIA driver; do not install a Linux display driver inside WSL |
| PyTorch reports CUDA unavailable | `which python`, whether the wheel includes CUDA, and driver compatibility |
| `No module named 'dotenv'` | Activate `.venv`, run `git pull --ff-only`, then reinstall `requirements-inference.txt`; the missing dependency has been added |
| Model import check fails | Keep the full traceback and resolve dependencies before continuing to downloads or inference |
| `curl: (18)` or missing ZIP central directory | Keep the incomplete ZIP and rerun the validation download block in step 8; do not redownload a completed checkpoint |
| Only `global_encoder.fc` has a 12/6 shape mismatch | Run `git pull --ff-only` for the legacy auxiliary-head compatibility fix, then rerun inference; strict loading remains enabled |
| Other checkpoint keys do not match | Check the submodule commit and the 2024 checkpoint; retain strict validation |
| `weights_only` loading fails | Keep the error and inspect the official checkpoint format before changing safe-loading behavior |
| CUDA out of memory | Use a less busy GPU or a shorter complete scan; the two GPUs' memory is not automatically combined |
| Process is `Killed` without a CUDA OOM error | Check WSL memory with `free -h`; changing the host's WSL memory allocation is a separate step |
| Output files already exist | Use a new output directory and preserve the previous experiment |
| Preview still uses the old interface | Regenerate it with a new `--output` path and open that new HTML; updating code does not rewrite existing HTML |

## Official references

- [Microsoft Remote Tunnels](https://code.visualstudio.com/docs/remote/tunnels)
- [Microsoft WSL commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)
- [VS Code CLI command source](https://github.com/microsoft/vscode/blob/main/cli/src/commands/args.rs)
- [Remote - Tunnels extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode.remote-server)
- [NVIDIA CUDA on WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)
- [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Install Python with uv](https://docs.astral.sh/uv/guides/install-python/)
- [Previous PyTorch installation combinations](https://pytorch.org/get-started/previous-versions/)
