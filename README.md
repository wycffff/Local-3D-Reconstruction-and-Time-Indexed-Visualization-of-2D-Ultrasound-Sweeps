# Local 3D Reconstruction and Time-Indexed Visualization of 2D Ultrasound Sweeps

二维超声扫查的局部三维重建与时间索引可视化研究原型。

**当前阶段：准备复现 DualTrack 2024。尚未完成真实超声数据上的模型推理验证。**

先用作者提供的预训练权重和 TUS-REC2024 配套数据处理一条完整扫查，得到预测位姿；随后查看三维布局，再尝试其他视频与时间轴展示。

## 从哪里开始

- **INSIGHT 双 RTX 2080 Ti / Windows + WSL2：** [远程隧道、项目同步与逐步测试](docs/INSIGHT_SETUP.md)。
- 已有 Linux GPU 环境：[首轮模型运行说明](FIRST_RUN.md)。

```bash
git clone --recurse-submodules https://github.com/wycffff/Local-3D-Reconstruction-and-Time-Indexed-Visualization-of-2D-Ultrasound-Sweeps.git ultrasound-sweeps
cd ultrasound-sweeps
```

## 目录

| 文件 | 用途 |
|---|---|
| `external/DualTrack` | 官方上游 Git 子模块，固定提交，保留原许可 |
| `requirements-inference.txt` | 首轮推理依赖候选 |
| `scripts/check_gpu.py` | Python / CUDA 环境及实际小运算检查 |
| `scripts/list_sweeps.py` | 列出符合首轮输入要求的 HDF5 扫描 |
| `scripts/infer_one_sweep.py` | 只读图像，严格加载权重，保存预测位姿 |

`data/`、`checkpoints/`、`results/`、本地环境与参考视频不进入 Git。GitHub 同步代码；VS Code 隧道负责连接学校电脑并在那里执行代码。

首轮默认使用一张 GPU。两张 2080 Ti 的显存不会在这个脚本中自动合并。

## 验证状态与来源

学校 WSL 已通过 CUDA 运算和 DualTrack 导入检查，配套验证集已下载并检查完整性。启动脚本已修复官方权重的旧辅助头形状差异；本地 CPU 使用真实官方权重确认全部 854 项严格加载且值一致，32 帧合成输入的完整模型前向输出为 `(1,31,6)` 且数值有限。学校 GPU 的完整真实扫查推理和几何质量仍待验证。

DualTrack 上游固定为 `b904a3d41f4d1ca1ba1c192e2b213756650cfd15`。模型、上游代码和数据分别遵守原作者条款；本仓库不重新发布权重或数据。

- [DualTrack](https://github.com/ImFusionGmbH/DualTrack)
- [DualTrack 论文](https://arxiv.org/html/2509.09530v2)
- [TUS-REC2024 验证集](https://zenodo.org/records/12979481)
