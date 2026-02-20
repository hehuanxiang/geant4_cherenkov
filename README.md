# Geant4 Cherenkov 光子模拟系统

基于 Geant4 的 6MV 医用直线加速器光子束在水体中产生 Cherenkov 光的蒙特卡洛模拟，输出光子相空间（PHSP）与可选剂量沉积，并可构建 Cherenkov/Dose 体素核。

---

## 一、项目结构

### 1.1 目录与文件概览

```
geant4_cherenkov/
├── config.json                 # 运行配置（几何、输出路径、二进制/CSV 等）
├── config_example.json         # 配置模板
├── README.md                   # 本文件
├── BINARY_OUTPUT_README.md     # 二进制输出格式说明
│
├── scripts/
│   ├── build.sh                # 配置 Geant4 环境 + CMake 构建
│   ├── run_simulation.sh       # 统一运行入口（test / full / custom）
│   ├── run_kernel_after_full.sh # full 后一键生成 Cherenkov 核 + Dose 核
│   └── analyze_run_meta.py     # 查看 *.run_meta.json 概要
│
├── macros/
│   └── run_base.mac            # 基础宏（verbosity、种子、initialize，不含 beamOn）
│
├── analysis/
│   ├── build_cherenkov_kernel.py  # 从 .phsp 构建 3D Cherenkov 体素核
│   └── build_dose_kernel.py      # 从 .dose 构建 3D Dose 体素核
│
├── output/                     # 模拟输出（路径由 config 中 output_file_path 决定）
│   ├── *.phsp, *.header        # Cherenkov 光子二进制
│   ├── *.dose, *.dose.header   # 能量沉积（enable_dose_output 时）
│   └── *.run_meta.json         # Run 元数据（事件数、光子数等）
│
├── kernel_output/              # Cherenkov 体素核（build_cherenkov_kernel.py）
├── dose_kernel_output/         # Dose 体素核（build_dose_kernel.py）
│
├── plot/                       # 分析脚本生成的图表
├── log/                        # 模拟运行日志
├── build/                      # CMake 构建目录，含 CherenkovSim 可执行文件
├── src/                        # C++ 源文件（CherenkovSim, RunAction, EventAction 等）
├── include/                    # C++ 头文件
├── read_binary_phsp.py         # 二进制 PHSP 读取工具
├── analyze_cherenkov.py        # 完整数据分析（全量光子）
└── analyze_cherenkov_fast.py   # 快速分析（采样，推荐）
```

### 1.2 三层架构

- **核心模拟层（C++ / Geant4）**  
  `CherenkovSim` 入口，`DetectorConstruction`（世界+水体）、`PHSPPrimaryGeneratorAction`（PHSP 粒子源）、`RunAction`/`EventAction`/`SteppingAction`（运行与光子记录）、`PhotonBuffer`（二进制缓冲）、`Config`（读取 config.json）。

- **运行管理层（脚本与宏）**  
  `build.sh` 构建；`run_simulation.sh` 调用 `CherenkovSim`（test/full/custom），写日志到 `log/`；`run_kernel_after_full.sh` 在 full 结束后按 config 输出路径依次跑 Cherenkov 核与 Dose 核；`run_base.mac` 仅做初始化，不含 `/run/beamOn`。

- **分析与文档层（Python）**  
  核构建（`build_cherenkov_kernel.py`、`build_dose_kernel.py`）、PHSP/run_meta 分析、二进制读取与可视化（`analyze_cherenkov*.py`、`read_binary_phsp.py`）、README 与 BINARY_OUTPUT_README。

---

## 二、用法速查

以下命令均假设项目根目录为 `/home/xhh2c/project/geant4_cherenkov`，按需替换。

### 2.1 构建（首次或修改 C++ 后）

```bash
cd /home/xhh2c/project/geant4_cherenkov
bash scripts/build.sh
```

### 2.2 运行模拟

```bash
# 快速测试（100 事件）
bash scripts/run_simulation.sh test

# 完整 PHSP（约 5230 万事件）
bash scripts/run_simulation.sh full

# 自定义事件数
bash scripts/run_simulation.sh custom --events 5000000
```

事件数由 `--mode test|full|custom` 与可选的 `--events N` 决定；脚本会调用 `CherenkovSim` 并写日志到 `log/simulation_YYYYMMDD_HHMMSS.log`。

### 2.3 full 跑完后生成 Cherenkov 核与 Dose 核

输出路径以 config 中 `output_file_path` 为准；若存在同前缀的 `.dose`，会同时生成 Dose 核。

```bash
bash scripts/run_kernel_after_full.sh
```

生成：`kernel_output/`（Cherenkov 核）、`dose_kernel_output/`（有 .dose 时）。

### 2.4 查看本次 Run 概要

```bash
python3 scripts/analyze_run_meta.py
# 或指定文件：
python3 scripts/analyze_run_meta.py output/cherenkov_photons_full.run_meta.json
```

### 2.5 直接调用可执行文件（高级）

```bash
cd /home/xhh2c/project/geant4_cherenkov/build
ln -sf ../config.json config.json

./CherenkovSim --config ../config.json --mode test --macro ../macros/run_base.mac
./CherenkovSim --config ../config.json --mode full --macro ../macros/run_base.mac
./CherenkovSim --config ../config.json --mode custom --events 5000000 --macro ../macros/run_base.mac
```

### 2.6 核的生成（仅 Cherenkov 或仅 Dose）

**仅 Cherenkov 核**（需有 .phsp 与同目录 run_meta 或传 `--n-primaries`）：

```bash
# 默认路径（从 config 读 output 前缀）
python3 analysis/build_cherenkov_kernel.py --config config.json

# 指定 PHSP 与输出目录
python3 analysis/build_cherenkov_kernel.py --phsp output/cherenkov_photons_full.phsp \
  --config config.json --output-dir kernel_output --n-primaries 52302569

# 仅 xy ∈ [-10, 10] cm
python3 analysis/build_cherenkov_kernel.py --config config.json --xy-range -10 10
```

**仅 Dose 核**（需有 .dose 与 run_meta）：

```bash
python3 analysis/build_dose_kernel.py --dose output/cherenkov_photons_full_with_dose.dose \
  --config config.json --output-dir dose_kernel_output
```

可使用 `--density-g-cm3` 指定 Gy 转换用密度（默认 1.0 g/cm³，水）。

### 2.7 数据分析（快速 / 完整）

```bash
# 快速可视化（采样，推荐）
python3 analyze_cherenkov_fast.py
python3 analyze_cherenkov_fast.py 2              # 仅图 2
python3 analyze_cherenkov_fast.py 1 5 10         # 图 1, 5, 10

# 完整分析（全量光子，耗时长）
python3 analyze_cherenkov.py
```

### 2.8 二进制输出配置与读取

- **配置**：在 `config.json` 的 `simulation` 中设 `output_format: "binary"`，`enable_cherenkov_output` / `enable_dose_output` 控制是否输出 Cherenkov/Dose；详见下文「二进制输出系统」。
- **读取 PHSP（v2，60 字节/记录）**：
  ```bash
  python3 read_binary_phsp.py output/cherenkov_photons_full.phsp
  ```
  或在 Python 中用 `np.fromfile(..., dtype=dt)`，字段含 `initX/Y/Z`、`finalX/Y/Z`、`finalEnergy`、`event_id`、`track_id`；详见 BINARY_OUTPUT_README.md。

---

## 三、详细介绍

### 3.1 模拟场景与物理过程

系统模拟 **6MV 医用直线加速器光子束打入水体产生的 Cherenkov 光**：

1. 从 Varian TrueBeam 6MV 相位空间（PHSP）读入初始粒子（光子、电子、正电子）
2. 粒子在**空气中传播**，再进入**水体**
3. 在水中发生康普顿散射、光电效应等，产生次级带电粒子
4. 当带电粒子速度超过介质光速时产生 **Cherenkov 光子**
5. 记录每个 Cherenkov 光子的产生/终止位置、方向、能量；可选记录能量沉积（Dose）

### 3.2 几何结构

- **世界**：150×150×150 cm³ 空气
- **水体**：默认 20×20×20 cm³，中心 (0, 0, 30) cm，即 Z 约 20–40 cm；折射率约 1.343–1.361
- **PHSP 源**：来自 TrueBeam 6MV，位置约 X ∈ [-30.37, 30.37] cm，Y ∈ [-30, 30] cm，Z ∈ [17.77, 27.35] cm，粒子主要沿 +Z

建议将水体改为 60×60×20 cm³ 以更好覆盖 PHSP 源范围（在 config 中改 `water_size_xyz_cm`）。

```
┌─────────────────────────────────────────────────────┐
│  World: 150×150×150 cm³ (Air)                       │
│    │    PHSP 源 (Z≈17.77~27.35 cm) → 空气中传播      │
│    │             ↓                                   │
│    │    ┏━━━━━━━━━━━━━━━━━━━━┓                      │
│    │    ┃ Water: 20×20×20 cm³ ┃ 中心 (0,0,30)       │
│    │    ┃ X:-10~+10, Y:-10~+10, Z:20~40 cm          │
│    │    ┃ Cherenkov 光产生并被记录                   │
│    │    ┗━━━━━━━━━━━━━━━━━━━━┛                      │
└─────────────────────────────────────────────────────┘
```

### 3.3 PHSP 粒子源与几何设计

- **源**：IAEA 二进制，每粒子 25 字节（类型、能量、位置 X/Y/Z、方向 U/V）
- **统计**：约 5230 万粒子，光子为主，电子/正电子少量；设计几何时需覆盖源空间并预留空气段

### 3.4 如何修改几何

修改 `config.json` 即可，无需重新编译：

- **水体尺寸**：`geometry.water_size_xyz_cm`，如 `[60, 60, 20]`
- **水体位置**：`geometry.water_position_cm`，如 `[0, 0, 30]`
- **世界大小**：`geometry.world_size_xyz_cm`
- **光学性质**：`water.optical_properties`（折射率、吸收长度等）

### 3.5 模拟记录的信息与输出位置

- **Cherenkov 输出**：由 `simulation.output_file_path` 决定前缀，二进制时为 `*.phsp` + `*.header`，CSV 时为 `*.csv`。
- **CSV 列**（若用 CSV）：InitialX/Y/Z、InitialDirX/Y/Z、FinalX/Y/Z、FinalDirX/Y/Z、FinalEnergyeV（eV）。
- **Dose 输出**：`output_format: "binary"` 且 `enable_dose_output: true` 时，同前缀生成 `*.dose`、`*.dose.header`。
- **run_meta**：与输出同目录的 `*.run_meta.json`，含事件数、总光子数、总沉积数等，供核构建脚本使用。

| 列名 | 单位 | 说明 |
|------|------|------|
| InitialX/Y/Z | cm | Cherenkov 光子产生位置 |
| InitialDirX/Y/Z | - | 光子初始方向（单位向量） |
| FinalX/Y/Z | cm | 光子终止位置 |
| FinalDirX/Y/Z | - | 光子终止方向 |
| FinalEnergyeV | eV | 光子终止能量 |

输出目录通常为 `output/`；核输出在 `kernel_output/`、`dose_kernel_output/`；日志在 `log/`。

### 3.6 物理配置

- **物理列表**：FTFP_BERT + G4EmStandardPhysics_option4 + G4OpticalPhysics（含 Cherenkov）
- **Cherenkov 阈值**：电子在水中约 **0.18 MeV**；光子不直接产生 Cherenkov

### 3.7 二进制输出系统

- **v2 格式**：60 字节/光子，little-endian；含 event_id、track_id（-1 表示未知）；详见 BINARY_OUTPUT_README.md。
- **三种模式**：Cherenkov ONLY、Dose ONLY、Both；由 `enable_cherenkov_output` 与 `enable_dose_output` 控制。
- **性能**：相对 CSV 写入略快、读取快约 68 倍，文件体积约省 70%。

| 特性 | CSV | 二进制 | 改进 |
|------|-----|--------|------|
| 文件大小 | ~227 GB | ~68 GB | 省约 70% |
| 读取速度 | ~20 min | ~17 s | 快约 68 倍 |

配置示例（Cherenkov + Dose 同时输出）：在 `simulation` 中设 `output_format: "binary"`、`enable_cherenkov_output: true`、`enable_dose_output: true`、`output_file_path` 为所需前缀。

### 3.8 数据分析说明

- **analyze_cherenkov_fast.py**：采样模式，生成多张分布图（能量、位置、方向、位移、相关性、3D、聚类等），推荐日常使用。
- **analyze_cherenkov.py**：全量光子，耗时长，适合最终统计。
- 图表输出在 `plot/`，编号 01–15 对应不同分析内容。

### 3.9 Cherenkov 体素核（Kernel）

- **含义**：K(x,y,z) = 体素内光子计数 / N_primaries，即每原粒子每体素的 Cherenkov 产额（仅用产生位置）。
- **输入**：`.phsp`、同目录 `.run_meta.json`（或 `--n-primaries`）、`config.json`（水体几何）。
> 本项目当前采用单粒子源（每 event 1 primary），因此 N_primaries = events。
- **输出文件**：

| 文件名 | 含义 |
|--------|------|
| kernel_01_counts.npy | 体素内原始光子计数 |
| kernel_02_normalized.npy | K = counts / N_primaries |
| kernel_03_uncertainty.npy | Poisson 不确定度 σ |
| kernel_04_voxel_edges.npz | 体素边界 x_edges, y_edges, z_edges |
| kernel_stats.json / .txt | 统计（photons_outside_grid、fraction_outside 等） |
| plot_01～04 | xy 切片、xz 切片、深度 K(z)、径向 K(r) |

- **Dose 核**：由 `build_dose_kernel.py` 生成到 `dose_kernel_output/`。
  - **原始 MeV kernel 保持不变**：kernel_01～04（能量和、归一化 MeV/primary/voxel、不确定度、体素边界）及 plot_01～04（MeV 图）语义与文件名均不变。
  - **新增 Gy 派生输出**：`kernel_05_dose_Gy_per_primary.npy`（单位 Gy/primary/voxel），以及 4 张 Gy 图 plot_05～08（xy 切片、xz 切片、深度曲线、径向曲线）。转换公式：体素剂量 Gy = 体素能量 MeV × 1.602176634e-10 /（密度 g/cm³ × 体素体积 cm³）；质量 kg = 质量 g/1000。
  - **参数 `--density-g-cm3`**：用于上述 Gy 转换的密度，默认 1.0 g/cm³（水）；仅影响 kernel_05 与 Gy 图，不改变 Cherenkov 或 MeV 核。
- **使用核数组示例**：

```python
import numpy as np
counts = np.load("kernel_output/kernel_01_counts.npy")
K     = np.load("kernel_output/kernel_02_normalized.npy")
edges = np.load("kernel_output/kernel_04_voxel_edges.npz")
x_c = (edges["x_edges"][:-1] + edges["x_edges"][1:]) / 2
# 同理 y_c, z_c；K[i,j,k] 即体素 (i,j,k) 的归一化核
```

### 3.10 常见问题

- **没有 Cherenkov 光子**：检查粒子是否进入水体、电子能量是否高于阈值、物理列表是否含光学过程；可 `grep -i cherenkov log/simulation_*.log`。
- **CSV 与二进制切换**：修改 `config.json` 的 `output_format` 为 `"csv"` 或 `"binary"`。
- **只输出某能量范围**：需改 `SteppingAction.cc` 在记录前加能量判断。

### 3.11 磁盘、版本与日志

- **磁盘**：完整 PHSP 约 68 GB；图表约 22 MB；源码与构建 <1 GB。
- **版本**：v3.1（PHSP v2、run_kernel_after_full 双核）；v3.0（二进制）；v2.0（CSV 多线程）；v1.0（基础）。
- **日志**：`log/simulation_*.log`；关键字如 `Config loaded successfully`、`PHSP Statistics`、`Progress:`、`Binary output enabled`。

---

**最后更新**: 2026-02-18
