# Geant4 Cherenkov 光子模拟系统

## 项目架构总览

这个项目可以理解为三层结构：

- **核心模拟层（C++ / Geant4）**  
  - `CherenkovSim.cc`：程序入口，创建 `RunManager`，注册几何、物理和各类 Action，并根据运行模式（test/full/custom）统一发出 `/run/beamOn`。  
  - `include/*.hh` + `src/*.cc`：  
    - `DetectorConstruction`：世界体积 + 水箱几何。  
    - `PHSPPrimaryGeneratorAction`：从 PHSP 文件读入粒子。  
    - `RunAction`：控制一次 Run 的开始/结束、输出文件与统计信息，并写出 `*.run_meta.json` 元数据。  
    - `EventAction`：记录每个 Event 内产生/终止的 Cherenkov 光子。  
    - `SteppingAction`：在步进过程中判断何时记录光子终止状态。  
    - `PhotonBuffer`：二进制输出缓冲管理（TOPAS 风格 Master/Worker 结构）。  
    - `Config`：负责读取 `config.json` 并为几何 / 模拟提供参数。

- **运行管理层（脚本 & 宏）**  
  - `scripts/build.sh`：配置 Geant4 环境 + CMake 构建。  
  - `scripts/run_simulation.sh`：统一的运行入口（`test` / `full` / 自定义），负责：  
    - 配置 Geant4 环境与数据路径；  
    - 选择基础宏 `macros/run_base.mac`（只做初始化，不含 `beamOn`）；  
    - 以 `--mode test|full|custom` 方式调用 `CherenkovSim`；  
    - 记录日志到 `log/simulation_YYYYMMDD_HHMMSS.log`。  
  - `macros/run_base.mac`：设置 verbosity、随机数种子、`/run/initialize` 等，**不包含 `/run/beamOn`**。

- **分析与文档层（Python & 报告）**  
  - `scripts/analyze_run_meta.py`：从 `*.run_meta.json` 中查看一次 Run 的概要（事件数、光子数、时间、线程数等）。  
  - `analyze_input_phsp.py` 及 `analysis_input_phsp/*`：对输入 PHSP 的统计分析与报告生成。  
  - 其他分析脚本（如二进制输出读取、结果可视化，见文末“数据分析”部分）。  
  - 本 `README.md` 与相关文档：说明项目架构、运行方式、几何和物理配置等。

下面先给出**快速使用方式**，再详细介绍模拟场景和物理配置。

---

## 快速开始：如何运行这个项目

### 构建工程（首次或修改 C++ 代码后）

```bash
cd /home/xhh2c/project/geant4_cherenkov
bash scripts/build.sh
```

### 使用脚本运行模拟（推荐）

#### 快速测试（100 个事件，`--mode test`）

```bash
cd /home/xhh2c/project/geant4_cherenkov
bash scripts/run_simulation.sh test
```

#### 完整 PHSP（52,302,569 个事件，`--mode full`）

```bash
cd /home/xhh2c/project/geant4_cherenkov
bash scripts/run_simulation.sh full
```

脚本内部会调用：

- `./CherenkovSim --config ../config.json --mode test --macro ../macros/run_base.mac`  
  或  
- `./CherenkovSim --config ../config.json --mode full --macro ../macros/run_base.mac`

事件数可通过追加 `--events N` 覆盖（例如把 test 改成 1000 事件）。

### 直接调用可执行文件（高级用法）

在 `build/` 目录下，你也可以直接控制运行模式和事件数：

```bash
cd /home/xhh2c/project/geant4_cherenkov/build
ln -sf ../config.json config.json

# 快速测试（100 事件）
./CherenkovSim --config ../config.json --mode test --macro ../macros/run_base.mac

# 完整 PHSP（默认 52,302,569 事件）
./CherenkovSim --config ../config.json --mode full --macro ../macros/run_base.mac

# 自定义事件数（例如 5,000,000）
./CherenkovSim --config ../config.json --mode custom --events 5000000 --macro ../macros/run_base.mac
```

### 查看本次 Run 的概要信息

每次运行结束后，`RunAction` 会在输出前缀旁边写一个元数据文件，例如：

- `output/cherenkov_photons_full.run_meta.json`

可以用辅助脚本快速查看概要：

```bash
cd /home/xhh2c/project/geant4_cherenkov
python3 scripts/analyze_run_meta.py
```

---

## 模拟场景概述

## 模拟场景概述

这个模拟系统模拟**6MV医用线性加速器的光子束打入水体时产生的Cherenkov光**。

**物理过程**：
1. 从Varian TrueBeam 6MV加速器的相位空间(PHSP)文件中读取初始粒子（光子、电子、正电子）
2. 粒子先在**空气中传播**
3. 进入**水体**后与水分子相互作用（康普顿散射、光电效应等）
4. 产生**Cherenkov光子**（当带电粒子速度超过介质光速时产生）
5. 记录每个Cherenkov光子的**产生位置、方向、能量和终止位置**

---

## 几何结构

```
┌─────────────────────────────────────────────────────┐
│                                                      │
│           World: 150×150×150 cm³ (Air)             │
│           ├─ Density: 1.29 mg/cm³ (N₂, O₂)         │
│           │                                         │
│           │    ✓ PHSP粒子源位置                      │
│           │    │ (Z = 17.77 ~ 27.35 cm)            │
│           │    │ X = -30.37 ~ +30.37 cm            │
│           │    │ Y = -30 ~ +30 cm                  │
│           │    ↓                                     │
│           │    ┌──────────────────────┐             │
│           │    │ 粒子在空气中传播      │             │
│           │    │ (Z = 17.77 ~ 20 cm) │             │
│           │    └──────────────────────┘             │
│           │             ↓                           │
│           │    ┏━━━━━━━━━━━━━━━━━━━━┓              │
│           │    ┃ Water: 20×20×20 cm³┃              │
│           │    ┃ 中心: (0, 0, 30)  ┃              │
│           │    ┃ 范围:             ┃              │
│           │    ┃ • X: -10 ~ +10 cm ┃              │
│           │    ┃ • Y: -10 ~ +10 cm ┃              │
│           │    ┃ • Z: 20 ~ 40 cm   ┃              │
│           │    ┃ • Density: 1.0 g/cm³              │
│           │    ┃ • 折射率: 1.343~1.361             │
│           │    ┃                   ┃              │
│           │    ┃ → Cherenkov光产生  ┃              │
│           │    ┃   并被记录        ┃              │
│           │    ┗━━━━━━━━━━━━━━━━━━━━┛              │
│           │                                        │
│           └─────────────────────────────────────────┘
```

---

## 为什么这样设置几何？

### PHSP粒子源特性
从Varian TrueBeam 6MV PHSP文件提取的真实数据：
```
粒子源范围：
  • X: -30.37 ~ +30.37 cm（约60cm）
  • Y: -30 ~ +30 cm（60cm）
  • Z: 17.77 ~ 27.35 cm
粒子运动方向：   大部分沿+Z方向（W > 0.95）
粒子类型：       光子(99.4%)、电子(1.1%)、正电子(0.04%)
粒子数量统计：
  • 光子: 51,692,883个，平均能量1.232 MeV
  • 电子: 589,933个，平均能量0.7595 MeV
  • 正电子: 19,754个，平均能量1.165 MeV
总粒子数：       52,302,569 粒子
```

### 设置设计逻辑
1. **水体大小 20×20×20 cm³**
   ⚠️ **注意**：这是初始设置，与实际PHSP源范围(±30cm)不匹配
   - 建议根据实际需求调整为60×60×20 cm³
   
2. **水体位置 Z = 30 cm（中心）**
   - Z范围: 20 ~ 40 cm
   - 完全包含PHSP源位置(17.77 ~ 27.35cm)
   - 粒子先在空气中传播，再进入水体
   
3. **建议改进**
   - 修改 `config.json` 中 `water_size_xyz_cm` 为 `[60, 60, 20]`
   - 这样可以完全捕获所有PHSP粒子
   
3. **空气环境**
   - 模拟医学线性加速器到患者之间的空气间隙
   - 粒子能量损失和方向偏转
   
4. **世界大小 150×150×150 cm³**
   - 足够大来容纳整个几何
   - 确保粒子不会逸出边界

---

## PHSP粒子源详细信息

### 源的物理意义
PHSP是来自**Varian TrueBeam 6MV医用直线加速器**的真实粒子分布数据：
- 采集位置：加速器射线头下方，患者独立相位空间
- 主要成分：6MeV宽带X光谱，经靶内部和初滤化器处理
- 应用：放疗计划验证、蒙特卡洛剂量计算

### 源数据格式（IAEA二进制）
每个粒子记录25字节：
```
[粒子类型(1B)] [能量(4B)] [位置X,Y,Z(3×4B)] [方向U,V(2×4B)]
    ↓           ↓                ↓                    ↓
  光子(1)      MeV             cm           方向余弦（单位向量）
  电子(2)
  正电子(3)
```

### 粒子典型参数示例
```
粒子类型: 光子
能量: 3.52 MeV
位置: (-5.42, 2.04, 27.06) cm
方向: (-0.195, 0.076, 0.978)  ← 主要沿+Z方向
```

---

## 如何修改几何结构

### 修改配置文件 `config.json`

#### 1. 改变水体尺寸（推荐：与PHSP源匹配）
```json
"geometry": {
  "world_size_xyz_cm": [150, 150, 150],
  "water_size_xyz_cm": [60, 60, 20],         // 改为60×60×20 cm 以匹配PHSP源范围
  "water_position_cm": [0.0, 0.0, 30.0],
  "check_overlaps": true
}
```

说明：
- X: 60 cm (覆盖 -30~+30 cm)
- Y: 60 cm (覆盖 -30~+30 cm)
- Z: 20 cm (从 20~40 cm，覆盖源的 17.77~27.35 cm)

#### 2. 改变水体位置
```json
"water_position_cm": [0.0, 0.0, 25.0]         // 改为Z=25
```

#### 3. 改变世界大小
```json
"world_size_xyz_cm": [200, 200, 200]          // 改为200×200×200
```

#### 4. 改变水的密度或光学性质
```json
"water": {
  "density_g_cm3": 1.0,
  "optical_properties": {
    "refractive_index": [1.35, 1.35, ...],    // 改变折射率
    "absorption_length_m": [10, 15, ...]      // 改变吸收长度
  }
}
```

### 修改后的效果
- **无需重新编译**！所有参数在运行时从`config.json`读取
- 直接修改配置文件并运行即可

---

## 如何运行模拟（更详细说明）

### 方法1：使用脚本（推荐）

#### 快速测试（100 个事件，`--mode test`）

```bash
cd /home/xhh2c/project/geant4_cherenkov
bash scripts/run_simulation.sh test
```

#### 完整模拟（52,302,569 个事件，`--mode full`）

```bash
cd /home/xhh2c/project/geant4_cherenkov
bash scripts/run_simulation.sh full
```

#### 使用自定义配置

```bash
cd /home/xhh2c/project/geant4_cherenkov
bash scripts/run_simulation.sh test --config /path/to/custom_config.json
```

> 脚本内部调用形式类似：
> - `./CherenkovSim --config ../config.json --mode test --macro ../macros/run_base.mac`  
> - `./CherenkovSim --config ../config.json --mode full --macro ../macros/run_base.mac`

### 方法2：直接运行可执行文件

#### 前置设置（首次需要）

```bash
source /home/xhh2c/Applications/scripts/geant4conf.sh
cd /home/xhh2c/project/geant4_cherenkov/build
ln -sf ../config.json config.json
```

#### 运行（批处理模式）

```bash
# 使用运行模式（推荐）：基础宏 + C++ 控制事件数
./CherenkovSim --config ../config.json --mode test   --macro ../macros/run_base.mac
./CherenkovSim --config ../config.json --mode full   --macro ../macros/run_base.mac
./CherenkovSim --config ../config.json --mode custom --events 5000000 --macro ../macros/run_base.mac
```

#### 交互模式

```bash
# 启动交互式 UI，自行在终端输入 /run/initialize、/run/beamOn 等命令
./CherenkovSim
```

---

## 模拟记录的信息

### 输出文件：CSV格式

位置：`config.json` → `simulation.output_file_path`（默认：`output/cherenkov_photons.csv`）

### CSV列说明

| 列名 | 单位 | 说明 |
|------|------|------|
| **InitialX** | cm | Cherenkov光子产生的X位置 |
| **InitialY** | cm | Cherenkov光子产生的Y位置 |
| **InitialZ** | cm | Cherenkov光子产生的Z位置 |
| **InitialDirX** | - | 光子初始方向X分量（单位向量） |
| **InitialDirY** | - | 光子初始方向Y分量 |
| **InitialDirZ** | - | 光子初始方向Z分量 |
| **FinalX** | cm | 光子最终位置X（吸收/逸出时） |
| **FinalY** | cm | 光子最终位置Y |
| **FinalZ** | cm | 光子最终位置Z |
| **FinalDirX** | - | 光子最终方向X分量 |
| **FinalDirY** | - | 光子最终方向Y分量 |
| **FinalDirZ** | - | 光子最终方向Z分量 |
| **FinalEnergyeV** | eV | 光子最终能量 |

### 记录流程
```
PHSP粒子进入水体
    ↓
粒子与水作用（Compton、光电等）
    ↓
●── 如果产生高速带电粒子 ───→ Cherenkov过程触发【记录】
      ↓
      └─→ 产生Cherenkov光子📸
          ├─ 记录产生时：位置、方向、光子轨迹号
          └─ 记录终止时：最终位置、最终方向、能量
              （吸收/逸出水体时）
```

---

## 输出文件位置

### 目录组织
```
geant4_cherenkov/
├── config.json                    ← 配置参数
├── output/
│   ├── cherenkov_photons.csv      ← 【主输出】Cherenkov光子数据
│   └── ...（其他可能的输出）
├── log/
│   ├── simulation_20260215_120330.log    ← 最新运行日志
│   └── ...（历史日志）
├── build/
│   └── CherenkovSim               ← 可执行文件
└── src/
    ├── CherenkovSim.cc
    ├── Config.cc
    ├── DetectorConstruction.cc
    ├── PHSPPrimaryGeneratorAction.cc
    ├── SteppingAction.cc
    └── ...
```

### 输出文件大小估计
- **100个事件**：~5-10 KB
- **10,000个事件**：~500 KB - 1 MB
- **100,000个事件**：~5-10 MB

---

## 物理配置

### 物理列表
- **基础**：FTFP_BERT（Fort-Forschungs TOPAS）
- **电磁**：G4EmStandardPhysics_option4（最佳精度）
- **光学**：G4OpticalPhysics（**包含Cherenkov过程**）

### Cherenkov阈值能量
- 电子在水中：约0.18 MeV
- 光子不产生Cherenkov光（电中性）

---

## 项目文件结构

### 核心脚本和工具

#### Python脚本
- `build_cherenkov_kernel.py` - 从二进制 PHSP 构建 3D Cherenkov 体素核 K(x,y,z)，输出 kernel_01~04 与 4 张图（见「Cherenkov 体素核的生成与使用」）
- `analyze_cherenkov.py` (22 KB) - 完整数据分析脚本（支持14亿光子）
- `analyze_cherenkov_fast.py` (21 KB) - 快速分析脚本（采样模式，推荐日常使用）
- `read_binary_phsp.py` (4.1 KB) - 二进制相空间文件读取工具

#### Shell脚本
- `build.sh` (2.0 KB) - 项目编译脚本
- `run_simulation.sh` (4.3 KB) - 模拟运行脚本（支持test/full模式）

#### 配置文件
- `config.json` - 当前运行配置
- `config_example.json` - 配置模板

#### 文档
- `README.md` - 项目主文档（本文件）
- `BINARY_OUTPUT_README.md` - 二进制输出格式说明

### 数据文件目录

#### output/ - 输出数据
- `cherenkov_photons_full.phsp` (68 GB) - 完整二进制相空间数据（1,399,500,645光子）
- `cherenkov_photons_full.header` - 二进制文件头描述
- `cherenkov_photons_full.run_meta.json` - Run 元数据（事件数、总光子数等，供 build_cherenkov_kernel.py 使用）

#### kernel_output/ - 体素核输出（由 build_cherenkov_kernel.py 生成）
- `kernel_01_counts.npy`、`kernel_02_normalized.npy`、`kernel_03_uncertainty.npy`、`kernel_04_voxel_edges.npz` - 核数组与体素边界
- `kernel_stats.json`、`kernel_stats.txt` - 统计信息（含 photons_outside_grid、边界外光子占比等，便于程序读取或人工查看）
- `plot_01_xy_slice_center_z.png` ～ `plot_04_radial_profile_Kr.png` - 四张核可视化图

#### plot/ - 生成图表
15个可视化图表（总计22 MB）：
- 01-08: 基础分布图（能量、位置、方向、位移）
- 09-10: 相关性分析
- 11-12: 3D交互式可视化（HTML）
- 13-15: 聚类分析和统计总结

#### log/ - 运行日志
模拟运行的详细日志文件

### 源代码结构

#### 核心组件 (src/ & include/)
- `PhotonBuffer.cc/hh` - 二进制缓冲管理（TOPAS风格）
- `RunAction.cc/hh` - 运行控制（支持CSV/Binary双模式）
- `EventAction.cc/hh` - 事件处理
- `SteppingAction.cc/hh` - 步进控制
- `DetectorConstruction.cc/hh` - 探测器几何
- `PhysicsList.cc/hh` - 物理列表（光学过程）
- `Config.cc/hh` - 配置管理
- `SpaceStatsManager.cc/hh` - 相空间统计

#### build/ - 构建目录
- CMake生成的构建文件
- 可执行文件: `CherenkovSim`

---

## 二进制输出系统（v3.0新特性）

### 性能优势

相比CSV格式的显著改进：

| 特性 | CSV格式 | 二进制格式 | 改进 |
|------|---------|-----------|------|
| **文件大小** | 227 GB | 67.83 GB | **节省70%** |
| **写入速度** | 5m 54s | 5m 36s | 快5% |
| **读取速度** | 19m 44s | 17.3s | **快68.4倍** 🚀 |

### 数据格式

- **编码**: IEEE 754 float32（小端序）
- **每光子大小**: 52字节（13个字段 × 4字节）
- **字段顺序**: 
  1. 初始位置 (X, Y, Z) - 12 bytes
  2. 初始方向 (DirX, DirY, DirZ) - 12 bytes
  3. 最终位置 (X, Y, Z) - 12 bytes
  4. 最终方向 (DirX, DirY, DirZ) - 12 bytes
  5. 最终能量 (microeV) - 4 bytes

### 使用二进制输出

#### 配置
在 `config.json` 中设置：
```json
{
  "simulation": {
    "output_format": "binary",
    "buffer_size": 100000,
    "output_file_path": ".../cherenkov_photons_full"
  }
}
```

#### 读取数据（Python）
```python
import numpy as np

# 读取二进制数据
data = np.fromfile('output/cherenkov_photons_full.phsp', dtype='float32')
data = data.reshape(-1, 13)

# 提取字段
initial_x = data[:, 0]      # cm
initial_y = data[:, 1]      # cm
initial_z = data[:, 2]      # cm
initial_dir_x = data[:, 3]  # 单位向量
# ... 其他字段
final_energy = data[:, 12]  # microeV

# 或使用提供的工具
python3 read_binary_phsp.py output/cherenkov_photons_full.phsp
```

详细说明请参考 [BINARY_OUTPUT_README.md](BINARY_OUTPUT_README.md)

---

## 数据分析

### 快速可视化（推荐）

生成所有15个图表（采样模式，速度快）：
```bash
python3 analyze_cherenkov_fast.py
```

生成特定图表：
```bash
python3 analyze_cherenkov_fast.py 2           # 仅生成图2
python3 analyze_cherenkov_fast.py 1 5 10      # 生成图1, 5, 10
```

### 利用 run_meta.json 做快速 Run 概览（新）

每次模拟结束后，`RunAction` 会在输出前缀旁边生成一个元数据文件，例如：

- 输出前缀：`output/cherenkov_photons_full`
- 元数据：  `output/cherenkov_photons_full.run_meta.json`

你可以使用辅助脚本快速查看这次 Run 的概要信息：

```bash
# 自动查找 output/ 里最近的 *.run_meta.json
python3 analyze_run_meta.py

# 或者显式指定某个 meta 文件
python3 analyze_run_meta.py output/cherenkov_photons_full.run_meta.json
```

示例输出包括：

- 时间戳、输出前缀、PHSP 文件路径  
- 线程数（配置值 / 实际值）  
- 事件数、总 Cherenkov 光子数、每事件平均光子数  
- Wall / CPU 时间与加速比、每秒事件数

### 完整数据分析

使用全部14亿光子数据（需要更长时间）：
```bash
python3 analyze_cherenkov.py
```

### 可视化内容

1. 能量分布
2. 初始位置X-Y平面
3. 初始位置Z分布
4. 方向分布
5. 位移距离
6. 方向变化角度
7. 最终位置X-Y平面
8. 最终位置Z分布
9. 位移vs能量
10. 位置相关性
11. 3D初始位置（交互式）
12. 3D相关性（交互式）
13. 空间聚类分析
14. 联合分布
15. 统计总结

---

## Cherenkov 体素核 (Kernel) 的生成与使用

本节说明如何从 Geant4 输出的 Cherenkov 光子二进制 PHSP 构建 **3D 体素核 K(x,y,z)**，以及生成的文件与图表的含义。

### 1. 核的物理意义

- **K(x,y,z)**：在体素 (x,y,z) 内，**平均每个原粒子（primary）产生的 Cherenkov 光子数**。
- 仅使用光子的 **产生位置**（InitialX, InitialY, InitialZ），不涉及终止位置或能量。
- 归一化：**K = counts / N_primaries**，其中 counts 为该体素内的光子计数，N_primaries 为模拟的总原粒子数。
- 用途：作为“每原粒子、每体素”的 Cherenkov 产生强度，可用于剂量/光产额卷积等后续分析。

### 2. 输入文件与使用方式

脚本 `build_cherenkov_kernel.py` 会**自动查找**以下文件（路径可由命令行覆盖）：

| 文件 | 来源/位置 | 用途 |
|------|-----------|------|
| **.phsp** | 与 `--phsp` 一致，默认 `output/cherenkov_photons_full.phsp` | 二进制光子记录。小端序 float32，每光子 52 字节、13 列；列 0,1,2 = InitialX, InitialY, InitialZ (cm)。 |
| **.run_meta.json** | 与 .phsp 同目录、同主文件名，如 `output/cherenkov_photons_full.run_meta.json` | 若存在：读取 `total_photons`（总光子数）与 `events`（N_primaries）。并与文件大小校验一致。 |
| **.header** | 与 .phsp 同目录、同主文件名，如 `output/cherenkov_photons_full.header` | 可选：若 run_meta 与 config 均无 N_primaries，可从此解析。 |
| **config.json** | 默认项目根目录 `config.json` | 读取 `geometry.water_size_xyz_cm`、`geometry.water_position_cm`，计算水模边界 (x,y,z 的 min/max) 与水体几何中心 (cx,cy,cz)，用于体素网格与切片/径向中心。 |

- **光子总数**：优先用 run_meta 的 `total_photons`，否则用「文件字节数 / 52」；并校验文件大小能被 52 整除。
- **N_primaries**：优先级为 run_meta 的 `events` → header 解析 → config 的 `simulation` → 命令行 `--n-primaries`；必须为正整数。

### 3. 核的生成流程（简要）

1. **确定水模边界**  
   由 config 的 `water_size_xyz_cm` [sx,sy,sz] 与 `water_position_cm` [cx,cy,cz] 计算：  
   `x_min = cx - sx/2`, `x_max = cx + sx/2`（y、z 同理）。若提供 `--xy-range MIN MAX`，则 x、y 边界改为 [MIN, MAX]，z 与水体中心不变。

2. **体素网格**  
   - 取三轴跨度最大者 L_max，目标约 100 格：`dv = L_max/100`，并限制在 [0.3, 0.8] cm。  
   - 各轴 bin 数：`n = round(span/dv)`，边用 `np.linspace(min, max, n+1)` 生成，保证端点严格等于 min、max。

3. **分块读 PHSP**  
   每次读 `--chunk-size` 条记录（默认 100 万），只取列 0,1,2 (InitialX,Y,Z)，用 `np.histogramdd(..., bins=(x_edges, y_edges, z_edges))` 累加到同一 3D 数组 **counts**。不将整文件载入内存，适合数十 GB 级文件。

4. **归一化与不确定度**  
   - **K** = counts / N_primaries → 存为 `kernel_02_normalized.npy`。  
   - **σ**（Poisson）= sqrt(counts) / N_primaries → 存为 `kernel_03_uncertainty.npy`（counts=0 处 σ=0）。

5. **输出**  
   所有结果写入 `--output-dir`（默认 `kernel_output/`）：4 个 kernel 数组/边 + 4 张 PNG 图；终端打印「Photons read / Photons in voxel grid」及汇总。

### 4. 输出文件说明：Kernel 数组

均保存在 `kernel_output/`（或你指定的 `--output-dir`）：

| 文件名 | 含义 | 形状/内容 |
|--------|------|-----------|
| **kernel_01_counts.npy** | 每个体素内的**原始光子计数**（仅统计 InitialX,Y,Z 落在该体素内的光子）。 | 3D 数组，形状 (nx, ny, nz)，与体素网格一致。 |
| **kernel_02_normalized.npy** | **归一化核 K**：K(i,j,k) = counts(i,j,k) / N_primaries。单位：photons per primary per voxel。 | 同上的 3D float 数组。 |
| **kernel_03_uncertainty.npy** | **Poisson 不确定度**：σ(i,j,k) = sqrt(counts(i,j,k)) / N_primaries；counts=0 处为 0。 | 同上的 3D float 数组。 |
| **kernel_04_voxel_edges.npz** | 体素 bin 的边界，用于由下标 (i,j,k) 还原到物理坐标。 | 键：`x_edges`, `y_edges`, `z_edges`；长度分别为 nx+1, ny+1, nz+1。 |
| **kernel_stats.json** | 核统计信息（JSON，便于程序解析）。含 `photons_read`、`photons_in_voxel_grid`、`photons_outside_grid`、`fraction_outside`、水模边界、网格形状、kernel 统计、run_info 等。 | 键值对结构，可用 `json.load()` 读取。 |
| **kernel_stats.txt** | 与 kernel_stats.json 相同内容的可读版（类似 header）。 | 纯文本，便于快速查看。 |

- **边界外的光子**：`photons_outside_grid = photons_read - photons_in_voxel_grid`，即 InitialX/Y/Z 落在体素边界外的光子数；`fraction_outside` 为占比。这些光子不会计入 counts。
- **计数守恒**：`kernel_01_counts.npy` 全数组之和 = `photons_in_voxel_grid`。

### 5. 输出图表说明（每张图代表什么）

四张图均基于 **K**（kernel_02_normalized），并采用 config 中的**水体几何中心 (cx, cy, cz)** 作为切片与径向中心。

| 文件名 | 含义 |
|--------|------|
| **plot_01_xy_slice_center_z.png** | **XY 平面切片**：取 z = cz（水体中心 z，如 30 cm）处的一层。横轴 x、纵轴 y，颜色 = 该 (x,y) 体素内的 K（photons per primary per voxel）。反映在水体中心深度处，横向平面上的 Cherenkov 产生强度分布。 |
| **plot_02_xz_slice_center_y.png** | **XZ 平面切片**：取 y = cy（水体中心 y，如 0 cm）处的竖直面。横轴 x、纵轴 z，颜色 = K。反映穿过水体中心的矢状面上，沿深度与水平方向的产生强度。 |
| **plot_03_depth_profile_Kz.png** | **深度分布 K(z)**：在每个 z 上，对 x、y 求和得到 Σ K(x,y,z)。纵轴：Σ K（单位 photons per primary），横轴：z (cm)。反映沿束流方向（深度）积分后的 Cherenkov 产额。 |
| **plot_04_radial_profile_Kr.png** | **径向分布 K(r)**：径向 r = sqrt((x−cx)² + (y−cy)²)（到水体中心在 xy 平面的距离）。按 r 分 bin，将各体素的 K 按 bin 求和。纵轴：K(r)（photons per primary，每径向 bin 内之和），横轴：r (cm)。反映相对束流轴的径向分布。 |

- 图 1、2 的 colorbar 单位均为「K (photons per primary per voxel)」。  
- 图 3、4 的纵轴单位均为「photons per primary」（积分或按 bin 求和后的量）。

### 6. 如何运行

```bash
cd /home/xhh2c/project/geant4_cherenkov

# 使用默认路径（需有 output/cherenkov_photons_full.phsp 与同目录 run_meta）
python3 build_cherenkov_kernel.py

# 仅分析 xy ∈ [-10, 10] cm（束流集中区域，约 96% 粒子）
python3 build_cherenkov_kernel.py --xy-range -10 10

# 指定 PHSP、config、输出目录、N_primaries（无 run_meta 时）
python3 build_cherenkov_kernel.py --phsp output/cherenkov_photons_full.phsp \
  --config config.json --output-dir kernel_output --n-primaries 52302569

# 小数据测试
python3 build_cherenkov_kernel.py --phsp output/cherenkov_photons_test.phsp \
  --output-dir kernel_output_test --xy-range -10 10
```

- 若存在同目录、同主文件名的 `.run_meta.json` 且含 `events` 与 `total_photons`，一般无需传 `--n-primaries`。  
- 终端会打印 **Photons read**（文件记录数）与 **Photons in voxel grid**（counts 之和），以及汇总中的「Mean photons per primary (file)」与「Mean photons per primary (in grid)」，便于核对口径。

### 7. 使用核数组的简单示例（Python）

```python
import numpy as np

# 加载
counts = np.load("kernel_output/kernel_01_counts.npy")
K      = np.load("kernel_output/kernel_02_normalized.npy")
sigma  = np.load("kernel_output/kernel_03_uncertainty.npy")
edges  = np.load("kernel_output/kernel_04_voxel_edges.npz")
x_edges = edges["x_edges"]
y_edges = edges["y_edges"]
z_edges = edges["z_edges"]

# 体素 (i,j,k) 的物理中心
x_c = (x_edges[:-1] + x_edges[1:]) / 2
y_c = (y_edges[:-1] + y_edges[1:]) / 2
z_c = (z_edges[:-1] + z_edges[1:]) / 2

# 例如：某体素的 K 与不确定度
i, j, k = 33, 33, 16
print(K[i, j, k], sigma[i, j, k])
```

---

## 常见问题

### Q1: 为什么没有生成Cherenkov光子？
**可能原因**：
- 粒子没有进入水体（检查Z位置）
- 粒子能量不足（电子需要> 0.18 MeV）
- 光学过程未启用（检查物理列表）

**检查方法**：
```bash
grep -i "cherenkov" log/simulation_*.log
grep -i "loaded.*particles" log/simulation_*.log
```

### Q2: 为什么二进制格式读取这么快？
二进制格式是原始内存格式，无需解析文本。关键优势：
- 直接内存映射，无需逐行解析
- NumPy优化的批量读取
- 文件大小减少70%，IO时间大幅降低

### Q3: 如何在CSV和二进制格式间切换？
修改 `config.json` 中的 `output_format` 字段：
- `"output_format": "csv"` - CSV文本格式（易读但慢）
- `"output_format": "binary"` - 二进制格式（快速推荐）

### Q4: 能否只输出特定能量范围的光子？
编辑 `src/SteppingAction.cc`，在记录前添加能量判断。

---

## 磁盘使用

- **项目总大小**: ~68 GB
- **主要占用**: 
  - 二进制数据文件: 68 GB (1,399,500,645光子)
  - 可视化图表: 22 MB
  - 源代码和构建文件: <1 GB
  - 日志文件: <100 MB

---

## 版本历史

- **v3.0** (2026-02-16): 二进制输出系统（TOPAS风格缓冲），68.4倍读取加速
- **v2.0** (2026-02-15): 线程安全CSV输出，多线程支持
- **v1.0** (初始版本): 基础Cherenkov模拟

---

## 日志文件说明

查看日志文件可以了解模拟的详细过程。关键字：
- `Config loaded successfully` → 配置加载成功
- `PHSP Statistics` → PHSP粒子统计
- `Progress:` → 模拟进度
- `Cherenkov:` → Cherenkov过程配置
- `Binary output enabled` → 二进制输出模式

---

**最后更新**: 2026-02-16

