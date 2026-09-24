# 第一轮：让 DualTrack 2024 预测一条超声扫查

学校 Windows + WSL2 双 2080 Ti 机器的完整隧道、克隆和测试步骤见 [INSIGHT 操作指南](docs/INSIGHT_SETUP.md)。

目标只有一个：加载作者权重，用配套数据的一条完整扫查，输出预测的帧间运动与三维轨迹。

当前状态（2026-09-24）：学校 WSL 的 CUDA 运算检查及 DualTrack 导入通过，作者权重下载完成，公开验证集 ZIP 完整性检查和解压通过；最短可用完整扫描为 318 帧。首次加载发现上游旧辅助头的 12/6 维差异，启动脚本已兼容，并在本地 CPU 上用真实官方权重验证全部 854 项严格加载且值一致。学校 GPU 的完整扫查推理及几何质量仍待验证。

## 已准备的文件

- `external/DualTrack`：官方源码，提交 `b904a3d41f4d1ca1ba1c192e2b213756650cfd15`，未修改。
- `scripts/check_gpu.py`：检查 Python、PyTorch、CUDA 与一次小矩阵运算。
- `scripts/infer_one_sweep.py`：只读取原始 HDF5 的 `frames`，不读取 `tforms`；严格检查权重匹配，保存预测数组。
- `scripts/list_sweeps.py`：从解压数据中列出适用于首轮脚本的完整扫描。
- `requirements-inference.txt`：依据源码整理的推理依赖候选，未做 GPU 运行验证。

## 机器选择

优先使用学校已有的 Linux x86-64 NVIDIA GPU 机器。Python 3.11；建议 12–16 GB 显存、16–32 GB 内存，磁盘预留约 25 GB。这些是首轮留余量的建议，不是作者公布的最低配置。Windows 的 NVIDIA 机器可以采用 WSL2 Ubuntu；首次不建议直接适配原生 Windows。

论文在 RTX Quadro 6000 上报告 546 帧推理显存占用小于 7 GB；不同长度、软件环境和预处理占用会变化。首轮无需多卡或从零训练。

NVIDIA 驱动与 CUDA 版 PyTorch 是关键。预编译 PyTorch 通常带有所需 CUDA 运行库；本流程没有主动编译自定义 CUDA 扩展，通常不需要另外安装完整 CUDA Toolkit。学校集群须在分配到的 GPU 节点/作业内运行检查与推理，不要在登录节点推理。

## 在目标 Linux 机器准备独立环境

将此项目目录复制到目标机器并进入目录。若没有复制 `external/DualTrack`，先从下面的官方仓库克隆，切换到上面的提交。

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

根据机器驱动和 GPU 架构选择 PyTorch 官方支持的 CUDA wheel。以下 cu126 是候选示例，不能仅凭它推断任意机器都兼容：

```bash
python -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r requirements-inference.txt
python -m pip check
python scripts/check_gpu.py --output results/environment.json
```

检查报告应包含 `cuda_ready: true`。这仅证明基础 CUDA 运算能运行，不证明模型已经成功。原仓库完整 requirements 包含许多训练/笔记本依赖，并同时列出 Pillow 和 Pillow_SIMD；这里避免整表盲装，保留推理涉及的版本。后续若需要调整，记录实际版本。

## 获取作者权重和一条配套扫描

仅从作者来源取得权重：

```bash
mkdir -p checkpoints data results
curl -fL --retry 3 https://downloads.imfusion.com/DualTrack/dualtrack_final.pt -o checkpoints/dualtrack_final.pt
```

使用 [TUS-REC2024 公开验证集](https://zenodo.org/records/12979481)，ZIP 约 4.8 GB；无需先下载完整训练集。保留该记录的使用条款和引用信息。在本地解压后选一个原始扫描 `.h5`，其中 `frames` 应是 `[N,H,W]` 的 uint8 灰度序列。选一条不超过 1024 帧的完整扫查作为首轮输入；不任意抽帧或剪短后当作作者原始结果。

```bash
python scripts/infer_one_sweep.py --input /absolute/path/to/one_scan.h5 --checkpoint checkpoints/dualtrack_final.pt --output-dir results/first_sweep
```

将上面的 `/absolute/path/to/one_scan.h5` 替换为实际文件，权重用 2024 版，不用 2025 微调版。

预期产生 `poses.npy`、`relative_motion.npy` 和 `metadata.json`。推理过程不读取参考位姿。毫米空间显示还需保留数据集的图像标定信息；仅有位姿数组不等于已经生成三维体积。模型加载、前向运行、几何合理性是分开的检查，先取得预测，再用参考结果排错，随后制作三维初稿。

若报 CUDA 不可用，先检查目标环境；若权重键不匹配，保留完整报错，不放宽为静默部分加载；若显存不足，记录 GPU、帧数及错误，再选择更短的完整扫描或更大显存机器。

## 依据

- [DualTrack 官方仓库和模型/权重表](https://github.com/ImFusionGmbH/DualTrack)
- [DualTrack 论文 v2，实验与推理资源](https://arxiv.org/html/2509.09530v2)
- [PyTorch 2.7.1 官方安装组合](https://pytorch.org/get-started/previous-versions/#v271)
- [PyTorch 官方论坛：运行库与驱动说明](https://discuss.pytorch.org/t/how-do-i-get-started-with-cuda-and-pytorch/223816)

本项目首轮仅做配套数据推理。后续顺序：查看预测轨迹和三维切片 → 探索其他超声视频 → 时间轴和残影展示。
