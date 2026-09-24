# 首条扫查成功后：检查结果与三维预览

学校终端已报告 318 帧完整扫查在 CUDA 上成功完成推理，并保存三个结果文件。下面使用这些结果，不重新运行模型。三维预览按预测位姿放置原始切片和像素点；这一步还没有做体素融合或准确度评价。

## 1. 每次开机启动隧道

学校 Windows 开机、登录后，打开 Ubuntu：

```bash
"$HOME/.local/share/vscode-cli/code" tunnel --name insight-ultrasound
```

保持此终端运行。在自己电脑的 VS Code 连接 `insight-ultrasound`，打开 `/home/yechuanwei/projects/ultrasound-sweeps`，新建远程终端。若隧道仍在运行，无需重复启动。

## 2. 更新代码并检查保存结果

```bash
cd ~/projects/ultrasound-sweeps
git pull --ff-only
source .venv/bin/activate
python scripts/inspect_result.py results/first_sweep
```

预期 `valid: true`，`frame_count: 318`，`shapes` 为 `[318,4,4]` 与 `[317,6]`，`checks` 全部为 true。输出同时列出推理耗时、峰值显存、GPU 型号，以及预测轨迹的路径长度。路径长度不是重建误差；检查通过说明保存结果数值自洽，不代表预测几何准确。

若检查失败，保留输出，不手动修正数组使其通过。

## 3. 生成可离线打开的 HTML

仅需额外安装一个可视化库，不改动 PyTorch/CUDA：

```bash
python -m pip install -r requirements-preview.txt
python scripts/build_preview.py --result-dir results/first_sweep
```

脚本从 `metadata.json` 查找同一条原始 HDF5，只读取 `frames` 和预测结果，不读取参考 tracking/tforms。当前像素尺寸仅适用于 TUS-REC 2024 的 480×640 数据，不能直接用于任意设备视频。

成功后生成 `results/first_sweep/preview.html`。默认从 318 帧中选 64 帧用于显示，每隔约 8 个原始像素取样；全部 318 帧的原始推理结果不变。HTML 内包含数据、图片和绘图库，下载到自己电脑后可以直接用 Chrome/Edge 离线打开。

已有同名 HTML 时不会覆盖；调整显示密度可以另存：

```bash
python scripts/build_preview.py --result-dir results/first_sweep --max-frames 96 --pixel-step 8 --output results/first_sweep/preview_dense.html
```

若原始文件只是搬了位置，可用 `--input /新的绝对路径/同一条扫查.h5`。不要替换成另一条形状相同的扫描；旧推理结果没有输入哈希，形状检查无法证明是同一文件。

## 4. 从远程 VS Code 打开

在学校项目目录的远程终端运行：

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory results/first_sweep
```

保持这个终端运行。在 VS Code 底部打开 **Ports / 端口**；看不到时，通过命令面板执行 `Ports: Focus on Ports View`。选择 **Forward a Port / 转发端口**，填写 `8000`，然后点击该端口的 **Open in Browser / 在浏览器中打开**。在目录列表里点击 `preview.html`。

使用 VS Code 给出的转发地址，不假定自己的电脑的 8000 端口始终可用。停止预览服务器用该终端的 `Ctrl+C`，不会删除 HTML 或推理结果。

## 5. 查看什么

- 拖动三维图旋转，滚轮缩放，查看切片是否形成连续的空间分布。
- 拖动帧滑条，观察二维图像、当前切片位置和历史点云是否同步。
- 点击播放；按“只看当前切片”或“全部采样帧点云”比较。
- 取消“显示三维中的当前切片”可避免不透明切片挡住历史点云。
- 点云亮度门限只控制显示哪些回声像素，不是组织分割。

时间轴显示原始帧编号，不是经过校准的秒数。历史点云是不同采集帧的叠加，不能据此声称观察到了同一个三维体积内组织的真实时间变化。

开发验证使用合成 HDF5 和已知位姿，已检查坐标、结果检查失败路径，以及浏览器离线打开、滑条、播放暂停、显示模式和切片开关。学校真实预测结果的外观仍需打开生成的 HTML 查看。
