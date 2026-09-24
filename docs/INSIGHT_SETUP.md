# INSIGHT 双 2080 Ti：连接、同步、首次推理

本指南按学校机器是 Windows + WSL2 Ubuntu、两张 RTX 2080 Ti 编写。以下每一步都标明在哪台电脑、哪个终端操作；如果学校机器其实是原生 Linux，可跳过 WSL 检查。

当前状态（2026-09-24，依据学校终端输出）：CUDA 矩阵运算通过，识别到两张 2080 Ti；`DualTrack imports OK`；验证 ZIP 完整性检查与解压通过，扫描列表最短为 318 帧。尚未完成真实模型推理。**单卡 2080 Ti 有 11 GB 显存，可作为首轮测试配置；两卡不会自动变成 22 GB。**最终能否处理所选完整序列，须实际检查可用显存。

## 每次开机后的快捷操作

目前使用手动启动方式。学校电脑开机并登录 Windows 后，打开 Ubuntu，运行：

```bash
"$HOME/.local/share/vscode-cli/code" tunnel --name insight-ultrasound
```

保留这个终端运行；通常不需要重新登录 GitHub。自己电脑 VS Code 用 `Remote Tunnels: Connect to Tunnel` 连接 `insight-ultrasound`，打开 `/home/yechuanwei/projects/ultrasound-sweeps`，再新建一个远程终端：

```bash
cd ~/projects/ultrasound-sweeps
source .venv/bin/activate
nvidia-smi
```

隧道进程仍在运行时，不需要重复启动。新建 Python 工作终端时重新激活 `.venv`；不用重新安装依赖或下载数据。后续协助本项目启动/继续测试时，应同时提醒上面的隧道启动命令。

VS Code 支持 `code tunnel service install`，但 WSL 内的服务并不等于 Windows 开机后已自动启动 Ubuntu；自动启动需另外配置。目前继续使用以上手动方式。[官方隧道说明](https://code.visualstudio.com/docs/remote/tunnels)

## 项目在 Windows 哪里，是否要换盘

2026-09-24：用户确认磁盘剩余约 105 GB，当前决定保留项目位置，空间不足时再考虑迁移。

项目位于 WSL 的 `/home/yechuanwei/projects/ultrasound-sweeps`。在学校电脑本机 Ubuntu 中运行下面命令，可在学校 Windows 资源管理器中打开同一目录：

```bash
cd ~/projects/ultrasound-sweeps
explorer.exe .
```

也可在学校 Windows 资源管理器地址栏输入 `\\wsl.localhost\`，选择实际 Ubuntu 发行版，进入 `home\yechuanwei\projects\ultrasound-sweeps`。这不是另一份副本。WSL2 的 Linux 文件通常保存在 `ext4.vhdx` 虚拟磁盘中，Windows 物理位置取决于安装方式，不能仅凭 Linux 路径认定在 C 盘。[WSL 文件访问](https://learn.microsoft.com/en-us/windows/wsl/filesystems)、[WSL 磁盘说明](https://learn.microsoft.com/en-us/windows/wsl/disk-space)

查看项目用量和 Windows 各盘剩余空间：

```bash
du -sh ~/projects/ultrasound-sweeps
df -h /mnt/c /mnt/d /mnt/e
```

`du` 不包含项目外的 Python、下载缓存和整个 Ubuntu；`df` 看 `Avail` 列。若空间充足，先完成第 9 步推理，不必为了首次测试迁移。长期扩充数据时，可以把整个 WSL 发行版迁到 D/E 盘，保持 `/home/...` 路径和现有虚拟环境。不要直接拖动 `ext4.vhdx`，也不建议把带 `.venv` 的工程直接搬到 `/mnt/d`；Linux 工具通常在 WSL 文件系统内运行更快。迁移安排在模型和隧道停止后，另按实际发行版名、WSL 版本和目标盘类型操作。

## 0. 两条连接分别做什么

| 通道 | 作用 |
|---|---|
| 自己电脑 VS Code → 隧道 → 学校 WSL | 编辑学校文件、在学校运行 Python 和 GPU |
| 自己电脑 Git ↔ GitHub ↔ 学校 Git | 手动 push/pull 同步代码与说明 |

隧道窗口里按保存，文件已经保存在学校机器。它不会同时更新自己电脑的另一份本地工作目录；要更新那一份，先在学校 commit/push，再在本地 pull。

先把学校主机插电睡眠设为“从不”，让下面的隧道终端持续运行。初期不设置后台服务。屏幕可以锁定；关机、休眠、注销 Windows 会话、关闭隧道进程或 `wsl --shutdown` 都可能中断连接。

## 1. 学校电脑 / Windows PowerShell：确认 WSL 与显卡

```powershell
wsl --list --verbose
nvidia-smi
```

成功标志：Ubuntu 那一行 VERSION 为 `2`；`nvidia-smi` 显示两张 2080 Ti。CUDA Version 是驱动支持能力的显示，不代表已安装完整 CUDA Toolkit。

若只出现 docker-desktop，说明还需安装工作用 Ubuntu。可在管理员 PowerShell 运行 `wsl --install -d Ubuntu-24.04`，完成提示中的重启和首次 Linux 用户创建。

若 Ubuntu 是 VERSION 1，使用列表中的真实发行版名转换，例如：

```powershell
wsl --set-version Ubuntu-24.04 2
```

需要更新 WSL 时运行 `wsl --update`。转换或更新操作在设置阶段完成，不要在模型运行中做。

打开 Windows 开始菜单里的 Ubuntu。也可运行 `wsl -d Ubuntu-24.04`，其中发行版名换成列表中实际名称。

## 2. 学校电脑 / Ubuntu：确认 Linux 能看到 GPU

```bash
uname -r
uname -m
printf '%s\n' "$WSL_DISTRO_NAME"
nvidia-smi
```

成功标志：内核包含 `microsoft` / `WSL2`，架构是 `x86_64`，发行版为 Ubuntu，且能看到显卡。

如果仅提示 `nvidia-smi: command not found`，试：

```bash
/usr/lib/wsl/lib/nvidia-smi
```

Windows 正常而 WSL GPU 检查失败时，先检查 WSL2、WSL 更新及 Windows NVIDIA 驱动。**不要在 WSL 安装 Linux NVIDIA 显示驱动**；WSL 使用 Windows 驱动。此项目的预编译 PyTorch 推理通常也不需要另装完整 CUDA Toolkit。[NVIDIA 官方 WSL 指南](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)

## 3. 学校电脑 / Ubuntu：启动 Linux 版 VS Code 隧道

```bash
sudo apt-get update
sudo apt-get install -y curl ca-certificates tar git unzip
mkdir -p "$HOME/.local/share/vscode-cli"
cd "$HOME/.local/share/vscode-cli"
curl -fL 'https://update.code.visualstudio.com/latest/cli-linux-x64/stable' -o vscode-cli.tar.gz
tar -xzf vscode-cli.tar.gz
./code --version
```

成功标志：显示 VS Code CLI 的版本。这里专门下载 Linux CLI；WSL 中直接敲裸 `code` 可能调用 Windows 的 VS Code 启动脚本，连接到不同环境。

然后登录：

```bash
"$HOME/.local/share/vscode-cli/code" tunnel user login --provider github
```

按终端给出的网页和设备验证码登录 GitHub `wycffff`。验证码由你自己输入登录网页。隧道登录与稍后的 Git 推送认证是两回事。

启动隧道：

```bash
"$HOME/.local/share/vscode-cli/code" tunnel --name insight-ultrasound
```

首次按提示阅读、接受服务器许可。成功后应输出类似 `https://vscode.dev/tunnel/insight-ultrasound` 的链接。**终端持续运行、没有回到命令提示符是正常现象。保留这个终端。**

## 4. 自己电脑 / VS Code：连接学校机器

1. 先用浏览器打开上一步终端输出的链接，登录同一个 GitHub `wycffff`；能打开远程编辑器即证明隧道可用。
2. 自己电脑的桌面 VS Code 按 `Ctrl+Shift+X`，安装微软 **Remote - Tunnels**，扩展 ID `ms-vscode.remote-server`。
3. 按 `Ctrl+Shift+P`，运行 `Remote Tunnels: Connect to Tunnel`。
4. 按提示用同一个 GitHub 登录，选择 `insight-ultrasound`。
5. 在打开的远程窗口中，点 Terminal → New Terminal。

在这个远程终端运行：

```bash
uname -r
printf '%s\n' "$WSL_DISTRO_NAME"
pwd
nvidia-smi
```

成功标志：是学校的 Linux / WSL 环境并显示 2080 Ti，而不是自己电脑的 PowerShell。若远程终端是 Windows，检查学校端是否确实从 Ubuntu 用 Linux CLI 全路径启动。

后续 Ubuntu 命令都可以在此远程终端完成。VS Code 隧道不需要先配置 SSH 或路由器端口转发。[微软 Remote Tunnels 文档](https://code.visualstudio.com/docs/remote/tunnels)

## 5. 远程 Ubuntu：克隆项目和固定的上游代码

```bash
mkdir -p "$HOME/projects"
cd "$HOME/projects"
git clone --recurse-submodules https://github.com/wycffff/Local-3D-Reconstruction-and-Time-Indexed-Visualization-of-2D-Ultrasound-Sweeps.git ultrasound-sweeps
cd ultrasound-sweeps
git status
git submodule status
```

成功标志：工作区干净；DualTrack 子模块提交以 `b904a3d` 开头。子模块状态开头若是 `-`，执行 `git submodule update --init --recursive`。

项目放在 `/home/<Linux用户名>/projects/ultrasound-sweeps`，使用 WSL Linux 文件系统。

在 VS Code 点 File → Open Folder，打开上述路径。可以先在终端运行 `pwd` 复制实际路径。重新开终端后应落在项目目录；无需在远程终端另运行 `code .`。

## 6. 远程 Ubuntu：创建 Python 3.11 独立环境

使用 uv 下载独立 Python，避免不同 Ubuntu 版本默认 Python 的差异；不修改系统 Python。

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

成功标志：Python 3.11.x，路径指向本项目 `.venv/bin/python`。以后新开终端都重新 `source .venv/bin/activate`。

安装与上游版本对应的 PyTorch：

```bash
python -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r requirements-inference.txt
python -m pip check
```

这里固定 cu126 作为首测组合，前提是学校 Windows NVIDIA 驱动兼容。它是 PyTorch 官方发布组合；尚未在你的学校电脑实跑。若报告驱动过旧，先处理 Windows 驱动，或按实际版本选择官方支持的其他 CUDA wheel，不要在 WSL 乱装驱动。[PyTorch 安装矩阵](https://pytorch.org/get-started/previous-versions/#v271)

## 7. 远程 Ubuntu：做 GPU 运算检查

```bash
python scripts/check_gpu.py --output results/environment.json
```

成功标志：`cuda_available` 为 true，`cuda_ready` 为 true，`cuda_test_value` 为 64.0，并列出显卡。

如需确认模型依赖能导入：

```bash
PYTHONPATH=external/DualTrack python -c "from src.models import get_model; print('DualTrack imports OK')"
```

这仍然只是依赖检查；接下来才验证真实权重与真实图像推理。

## 8. 远程 Ubuntu：下载作者权重和验证集

```bash
mkdir -p checkpoints data results
curl -fL --retry 3 https://downloads.imfusion.com/DualTrack/dualtrack_final.pt -o checkpoints/dualtrack_final.pt
```

权重下载完成后，单独执行下面整段。验证集下载中断时保留 ZIP，重新执行这段即可续传，不需要重新下载权重。每次失败后重新启动 `curl -C -`，按文件最新大小续传；全部尝试失败时停止，不会继续解压。

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

权重约 408 MB，验证 ZIP 约 4.8 GB，整个安装/解压建议预留 25 GB 空间。下载较慢或 HTTP 429 时保留已有部分，稍后恢复，不反复发起并行下载；也可从 [官方数据页面](https://zenodo.org/records/12979481) 手动下载。

`curl: (18)` 表示传输未完成，此时 `End-of-central-directory signature not found` 是解压不完整 ZIP 的后续报错。普通 `--retry` 不涵盖错误 18；上面的外层循环会重新发起续传。使用 `-o` 写入文件，不改为 `>` 或 `>>`。下载成功后先用 `unzip -tq` 检查完整性，检查通过才解压和列出扫描。[curl 官方说明](https://curl.se/docs/manpage.html#--continue-at)

成功标志：列出若干 `N frames /完整路径/某个扫描.h5`。脚本只选图像形状正确、2–1024 帧的完整原始扫查，跳过 landmark 文件；这一限制用于首轮启动脚本，不代表对所有版本/策略的普遍结论。

## 9. 远程 Ubuntu：选择一张卡跑第一次真实推理

先查看显卡使用情况：

```bash
nvidia-smi
```

选一张可用显存较多的卡，下面以 GPU 0 为例。保持序列完整，启动脚本从符合条件的扫描中选帧数最少的一条，降低首轮显存压力：

```bash
US_SWEEP="$(python scripts/list_sweeps.py data/tus_rec_2024_val --first)"
printf '%s\n' "$US_SWEEP"
CUDA_VISIBLE_DEVICES=0 python scripts/infer_one_sweep.py --input "$US_SWEEP" --checkpoint checkpoints/dualtrack_final.pt --output-dir results/first_sweep
```

需要用另一张卡时，把 `CUDA_VISIBLE_DEVICES=0` 改为 `1`。脚本内仍称它为逻辑 `cuda:0`，这属于正常映射，不表示选错卡。

成功标志：输出 `All checkpoint keys matched`，随后保存三个文件。程序仅读图像、不读参考位姿。

```bash
python -c "import numpy as np; p=np.load('results/first_sweep/poses.npy'); print('shape:', p.shape); print('finite:', np.isfinite(p).all()); print('first pose:', p[0])"
```

预期 `shape` 是 `(帧数, 4, 4)`，`finite` 为 True，首帧为单位矩阵。`relative_motion.npy` 是相邻帧运动，`metadata.json` 记录权重校验值、版本、耗时等。

**这证明程序完成了预测，不代表几何质量已经合格。下一步再用预测轨迹绘制三维切片并查看结果。**第一次结果保留；重跑时换 `--output-dir results/second_sweep`，脚本不会覆盖已有输出。

## 10. 日常同步代码

学校首次需要向 GitHub 推送时，在远程 Ubuntu 终端配置身份与认证：

```bash
git config user.name "Yechuan Wei"
git config user.email "157529217+wycffff@users.noreply.github.com"
sudo apt-get install -y gh
gh auth login
gh auth setup-git
```

登录时选择 GitHub.com、HTTPS、浏览器登录。公开仓库的 clone/pull 本来就不要求登录；这个认证用于 push。

每次开始编辑前：

```bash
git status
git pull --ff-only
git submodule update --init --recursive
```

有未提交改动时先提交自己的改动，不用强制重置。修改完成后检查并提交；下方是修改脚本和文档时的例子，只加入实际想同步的路径：

```bash
git diff
git add scripts docs README.md FIRST_RUN.md requirements-inference.txt
git diff --cached --stat
git commit -m "Update first-run experiment"
git push
```

回到自己电脑的项目文件夹，在本地 PowerShell 执行同样的 `git pull --ff-only`、`git submodule update --init --recursive` 即可获取代码。不要在 Remote 窗口里运行这一步却误认为更新了本地文件。

Git 只同步已提交的内容，不会实时双向同步。若 `pull --ff-only` 提示无法快进，保留报错并处理分支分歧，不用 `push --force`。`.venv`、原始数据、权重和结果已被忽略，各电脑分别维护；小结果可用 VS Code 远程资源管理器的 Download 下载查看。

## 故障定位速查

| 现象 | 检查层次 |
|---|---|
| 找不到隧道 | 两端 GitHub 是否相同；学校隧道进程、主机和网络是否在线 |
| 连接后是 PowerShell | 学校端是否启动了 Windows CLI；改用 Ubuntu 的 Linux CLI 全路径 |
| Windows 看得到 GPU，WSL 看不到 | WSL 版本/更新、Windows NVIDIA 驱动；不要在 WSL 装显示驱动 |
| PyTorch CUDA 为 False | `which python`、wheel 是否 CUDA 版、驱动是否兼容 |
| `No module named 'dotenv'` | 保持 `.venv` 激活，`git pull --ff-only` 后重跑 `python -m pip install -r requirements-inference.txt`；依赖已补入 |
| imports OK 失败 | 保留完整 traceback；先解决依赖，不继续下载/跑数据 |
| `curl: (18)` / ZIP 找不到中央目录 | 验证集未下载完整；保留 ZIP，重新执行第 8 步验证集续传整段，不重下已完成的权重 |
| checkpoint keys 不匹配 | 确认子模块提交及 2024 权重，保留严格检查 |
| `weights_only` 加载失败 | 保留报错；先核对官方 checkpoint 格式，不自动关闭安全加载 |
| CUDA out of memory | 换空闲卡或更短的完整扫描；两卡显存不会自动合并 |
| 进程被 Killed 而非 CUDA OOM | 检查 `free -h` 的 WSL 内存；调整主机 WSL 内存分配需另行处理 |
| 三个输出已有 | 使用新的输出目录，保留上一轮实验 |

## 官方参考

- [Microsoft Remote Tunnels](https://code.visualstudio.com/docs/remote/tunnels)
- [Microsoft WSL 命令](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)
- [VS Code CLI 命令源码](https://github.com/microsoft/vscode/blob/main/cli/src/commands/args.rs)
- [Remote - Tunnels 扩展](https://marketplace.visualstudio.com/items?itemName=ms-vscode.remote-server)
- [NVIDIA CUDA on WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)
- [uv 安装](https://docs.astral.sh/uv/getting-started/installation/)
- [uv 安装 Python](https://docs.astral.sh/uv/guides/install-python/)
- [PyTorch 历史安装组合](https://pytorch.org/get-started/previous-versions/)
