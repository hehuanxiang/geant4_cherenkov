# Geant4 Cherenkov 光子模拟系统

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

## 如何运行模拟

### 方法1：使用脚本（推荐）

#### 快速测试（100个事件）
```bash
cd /home/xhh2c/project/geant4_cherenkov
bash run_simulation.sh test
```

#### 完整模拟（100,000个事件）
```bash
bash run_simulation.sh full
```

#### 使用自定义宏文件
```bash
bash run_simulation.sh custom.mac
```

#### 使用自定义配置
```bash
bash run_simulation.sh test --config /path/to/custom_config.json
```

### 方法2：直接运行可执行文件

#### 前置设置（首次需要）
```bash
source /home/xhh2c/Applications/scripts/geant4conf.sh
cd /home/xhh2c/project/geant4_cherenkov/build
ln -sf ../config.json config.json
```

#### 运行（批处理模式）
```bash
# 使用默认配置
./CherenkovSim ../test.mac

# 使用自定义配置
./CherenkovSim --config ../config.json ../test.mac
```

#### 交互模式
```bash
# 启动交互式UI
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

