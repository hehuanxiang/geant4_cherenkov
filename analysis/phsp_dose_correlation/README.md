# Cherenkov–Dose 相关性分析图说明

本目录由 `analyze_phsp_dose_correlation.py` 生成。数值结果见 **correlation_summary.txt**，图说明如下。

## 1. yield_fit_photons_vs_dose.png（主图）

**Cherenkov yield 线性拟合图**

- **横轴**：Dose per event (MeV)；**纵轴**：Photons per event。
- 仅对 dose_per_event >= 阈值的事件做线性拟合 N = a·E + b；图中叠加拟合直线，并标注 slope a (photons/MeV)、intercept b、R²、global yield (ΣN/ΣE)。
- 散点超过 20 万时自动抽样绘制。用于物理可解释的产额与线性关系展示。

## 2. scatter_dose_vs_photons.png

**散点图：每个 primary 的剂量 vs 切伦科夫光子数**

- **横轴**：Dose per event (MeV)；**纵轴**：Photons per event。标题中给出 Pearson 相关系数；散点过多时抽样至 20 万点。

## 3. hist_photons_per_event.png

**直方图：每个 primary 的光子数分布**

- **横轴**：Photons per event（该 primary 产生的切伦科夫光子数）。
- **纵轴**：Count（有多少个 primary 落在该 bin）。
- **含义**：展示光子数在事件间的分布（离散性、偏度、是否有长尾）。
- **用途**：了解模拟的涨落特性，便于设置阈值或解释相关性。

## 4. hist_photons_over_dose.png

**直方图：光子数/剂量比（dose >= 阈值，并按分位数裁剪）**

- **横轴**：Photons per event / Dose per event (MeV)。仅对 dose_per_event >= 阈值的事件计算 ratio，再按 --ratio-clip-quantile 裁剪上尾，避免 dose→0 导致的长尾拉爆坐标轴。
- **用途**：观察单位剂量对应产额的分布是否集中。
