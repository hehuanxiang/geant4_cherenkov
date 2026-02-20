#!/usr/bin/env python3
"""
Cherenkov–Dose correlation analysis: read .phsp and .dose from the same Geant4 run,
aggregate per event, compute correlations, and plot scatter + histograms.

Usage:
  cd project/geant4_cherenkov/analysis && python3 analyze_phsp_dose_correlation.py
  or from project root: python3 analysis/analyze_phsp_dose_correlation.py
"""

import argparse
import os
import sys
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------------
# Binary format (little-endian), match .header / .dose.header
# -----------------------------------------------------------------------------
PHSP_DTYPE = np.dtype([
    ("initX", "<f4"), ("initY", "<f4"), ("initZ", "<f4"),
    ("initDirX", "<f4"), ("initDirY", "<f4"), ("initDirZ", "<f4"),
    ("finalX", "<f4"), ("finalY", "<f4"), ("finalZ", "<f4"),
    ("finalDirX", "<f4"), ("finalDirY", "<f4"), ("finalDirZ", "<f4"),
    ("finalEnergy", "<f4"),
    ("event_id", "<u4"),
    ("track_id", "<i4"),
])
DOSE_DTYPE = np.dtype([
    ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
    ("dx", "<f4"), ("dy", "<f4"), ("dz", "<f4"),
    ("energy", "<f4"), ("event_id", "<u4"), ("pdg", "<i4"),
])

# Sparse branch: if max_event_id > SPARSE_THRESHOLD * total_records, use compressed indices
SPARSE_THRESHOLD = 10
# 散点图最大绘制点数，超过则随机抽样
MAX_SCATTER_POINTS = 200_000


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _project_root():
    return os.path.dirname(_script_dir())


def _write_figure_readme(output_dir):
    """在图所在目录写入 README，说明三张图的含义。"""
    path = os.path.join(output_dir, "README.md")
    text = """# Cherenkov–Dose 相关性分析图说明

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
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _write_stats_txt(
    output_dir,
    *,
    phsp_path,
    dose_path,
    n_events,
    nonzero_photon_events,
    nonzero_dose_events,
    mean_ph,
    std_ph,
    mean_dose,
    std_dose,
    global_yield,
    slope_a,
    intercept_b,
    R2_fit,
    corr_pearson,
    p_pearson,
    corr_spearman,
    p_spearman,
    corr_electron_dose,
):
    """将 per-event 统计与相关性结果写入 output_dir/correlation_summary.txt。"""
    path = os.path.join(output_dir, "correlation_summary.txt")
    lines = [
        "Cherenkov–Dose 相关性分析结果",
        "================================",
        "",
        "输入文件",
        "--------",
        f"  phsp: {phsp_path}",
        f"  dose: {dose_path}",
        "",
        "Per-event 统计",
        "----------------",
        f"  n_events                = {n_events}",
        f"  nonzero_photon_events   = {nonzero_photon_events}",
        f"  nonzero_dose_events     = {nonzero_dose_events}",
        f"  mean photons per event  = {mean_ph:.6f}",
        f"  std photons per event   = {std_ph:.6f}",
        f"  mean dose per event (MeV) = {mean_dose:.6f}",
        f"  std dose per event (MeV)  = {std_dose:.6f}",
        "",
        "Global yield",
        "-------------",
        f"  global_yield (ΣN/ΣE) = {global_yield:.6f} photons/MeV" if global_yield is not None else "  global_yield = N/A (sum(dose) <= 0)",
        "",
        "线性拟合 (dose >= threshold)",
        "-----------------------------",
    ]
    if slope_a is not None and intercept_b is not None and R2_fit is not None:
        lines.append(f"  slope a (photons/MeV) = {slope_a:.6f}")
        lines.append(f"  intercept b = {intercept_b:.6f}")
        lines.append(f"  R² = {R2_fit:.6f}")
    else:
        lines.append("  N/A (样本不足或零方差)")
    lines.extend([
        "",
        "相关性（total dose vs photons）",
        "--------------------------------",
    ])
    if corr_pearson is not None and p_pearson is not None:
        lines.append(f"  Pearson  = {corr_pearson:.6f}  (p = {p_pearson:.4e})")
    else:
        lines.append("  Pearson  = N/A (零方差)")
    if corr_spearman is not None and p_spearman is not None:
        lines.append(f"  Spearman = {corr_spearman:.6f}  (p = {p_spearman:.4e})")
    else:
        lines.append("  Spearman = N/A (零方差)")
    lines.append("")
    lines.append("电子剂量 (pdg==11) vs photons")
    lines.append("-----------------------------")
    if corr_electron_dose is not None:
        lines.append(f"  corr_electron_dose (Pearson) = {corr_electron_dose:.6f}")
    else:
        lines.append("  corr_electron_dose = N/A (零方差)")
    lines.extend([
        "",
        "对比",
        "----",
        f"  corr_total_dose    = {corr_pearson if corr_pearson is not None else 'N/A'}",
        f"  corr_electron_dose = {corr_electron_dose if corr_electron_dose is not None else 'N/A'}",
        "",
    ])
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def parse_args():
    proot = _project_root()
    default_phsp = os.path.join(proot, "output", "cherenkov_photons_full_with_dose.phsp")
    default_dose = os.path.join(proot, "output", "cherenkov_photons_full_with_dose.dose")
    default_out = os.path.join(_script_dir(), "phsp_dose_correlation")
    p = argparse.ArgumentParser(
        description="Per-event Cherenkov vs dose correlation (Pearson/Spearman, scatter + histograms)."
    )
    p.add_argument("--phsp", default=default_phsp, help="Path to .phsp binary")
    p.add_argument("--dose", default=default_dose, help="Path to .dose binary")
    p.add_argument("--output-dir", default=default_out,
                   help="Directory for PNG outputs (default: analysis/phsp_dose_correlation)")
    p.add_argument("--dose-fit-threshold", type=float, default=0.05,
                   help="Dose per event threshold (MeV) for fit and ratio histogram (default: 0.05)")
    p.add_argument("--ratio-clip-quantile", type=float, default=99.5,
                   help="Clip ratio histogram at this quantile (default: 99.5)")
    return p.parse_args()


def main():
    args = parse_args()

    # ----- STEP 1: Read binary -----
    phsp = np.fromfile(args.phsp, dtype=PHSP_DTYPE)
    dose = np.fromfile(args.dose, dtype=DOSE_DTYPE)

    # Guard: empty data
    if len(phsp) == 0:
        print("错误: phsp 为空", file=sys.stderr)
        sys.exit(1)
    if len(dose) == 0:
        print("错误: dose 为空", file=sys.stderr)
        sys.exit(1)

    # ----- STEP 2: Per-event aggregation, aligned length -----
    max_event_id = max(int(phsp["event_id"].max()), int(dose["event_id"].max()))
    n_events = max_event_id + 1
    total_records = len(phsp) + len(dose)
    use_sparse = max_event_id > SPARSE_THRESHOLD * total_records

    if use_sparse:
        # Single shared event set and mapping so photons and dose stay aligned
        all_event_ids = np.union1d(
            np.unique(phsp["event_id"]),
            np.unique(dose["event_id"]),
        )
        phsp_compressed_idx = np.searchsorted(all_event_ids, phsp["event_id"])
        dose_compressed_idx = np.searchsorted(all_event_ids, dose["event_id"])
        n_events_actual = len(all_event_ids)

        photons_per_event = np.bincount(phsp_compressed_idx, minlength=n_events_actual)
        dose_per_event = np.bincount(
            dose_compressed_idx, weights=dose["energy"], minlength=n_events_actual
        )
    else:
        dose_compressed_idx = None  # not used in dense branch
        n_events_actual = n_events
        photons_per_event = np.bincount(phsp["event_id"], minlength=n_events)
        dose_per_event = np.bincount(
            dose["event_id"], weights=dose["energy"], minlength=n_events
        )

    # ----- STEP 3: Basic stats -----
    mean_ph = float(np.mean(photons_per_event))
    std_ph = float(np.std(photons_per_event, ddof=1)) if len(photons_per_event) > 1 else 0.0
    mean_dose = float(np.mean(dose_per_event))
    std_dose = float(np.std(dose_per_event, ddof=1)) if len(dose_per_event) > 1 else 0.0
    n_ev = n_events_actual
    nonzero_photon_events = int(np.count_nonzero(photons_per_event))
    nonzero_dose_events = int(np.count_nonzero(dose_per_event > 0))

    print("--- Per-event stats ---")
    print(f"n_events = {n_ev}")
    print(f"nonzero_photon_events = {nonzero_photon_events}")
    print(f"nonzero_dose_events = {nonzero_dose_events}")
    print(f"mean photons per event = {mean_ph:.4f}")
    print(f"std photons per event  = {std_ph:.4f}")
    print(f"mean dose per event (MeV) = {mean_dose:.6f}")
    print(f"std dose per event (MeV)  = {std_dose:.6f}")

    # Global yield: Σphotons / Σdose [photons/MeV]
    sum_dose = float(np.sum(dose_per_event))
    sum_ph = float(np.sum(photons_per_event))
    if sum_dose <= 0:
        print("Global yield: 不可计算（sum(dose_per_event) <= 0）")
        global_yield = None
    else:
        global_yield = sum_ph / sum_dose
        print(f"Global yield (ΣN/ΣE) = {global_yield:.4f} photons/MeV")

    # ----- STEP 4: Correlation (with zero-variance guard) -----
    if std_ph == 0 or std_dose == 0:
        print("相关系数不可计算（零方差）")
        corr_pearson = corr_spearman = None
        p_pearson = p_spearman = None
    else:
        corr_pearson, p_pearson = stats.pearsonr(photons_per_event, dose_per_event)
        corr_spearman, p_spearman = stats.spearmanr(photons_per_event, dose_per_event)
        print("--- Correlation (total dose vs photons) ---")
        print(f"Pearson  = {corr_pearson:.6f}  (p = {p_pearson:.4e})")
        print(f"Spearman = {corr_spearman:.6f}  (p = {p_spearman:.4e})")

    # 拟合用阈值筛选
    dose_fit_threshold = getattr(args, "dose_fit_threshold", 0.05)
    mask_fit = dose_per_event >= dose_fit_threshold
    n_fit = int(np.sum(mask_fit))
    slope_a = intercept_b = R2_fit = None
    if n_fit >= 2:
        x_fit = dose_per_event[mask_fit]
        y_fit = photons_per_event[mask_fit]
        if np.var(x_fit) > 0:
            res = stats.linregress(x_fit, y_fit)
            slope_a, intercept_b = res.slope, res.intercept
            R2_fit = res.rvalue ** 2
            print("--- Linear fit (dose >= threshold) ---")
            print(f"  slope a (photons/MeV) = {slope_a:.4f}, intercept b = {intercept_b:.4f}, R² = {R2_fit:.6f}")
        else:
            print("(Fit skipped: dose variance in fit sample is zero)")
    else:
        print(f"(Fit skipped: only {n_fit} events with dose >= {dose_fit_threshold} MeV)")

    # ----- STEP 5: Figures -----
    os.makedirs(args.output_dir, exist_ok=True)

    def _subsample_scatter(x, y, max_pts=MAX_SCATTER_POINTS):
        n = len(x)
        if n <= max_pts:
            return x, y
        rng = np.random.default_rng(42)
        idx = rng.choice(n, size=max_pts, replace=False)
        return x[idx], y[idx]

    # (1) Scatter（抽样以保持可读）
    x_plot, y_plot = _subsample_scatter(dose_per_event, photons_per_event)
    fig1, ax1 = plt.subplots()
    ax1.scatter(x_plot, y_plot, alpha=0.3, s=5, label="events")
    ax1.set_xlabel("Dose per event (MeV)")
    ax1.set_ylabel("Photons per event")
    title1 = "Dose vs Cherenkov photons per event"
    if corr_pearson is not None:
        title1 += f"  (Pearson r = {corr_pearson:.4f})"
    ax1.set_title(title1)
    if n_ev > MAX_SCATTER_POINTS:
        ax1.text(0.02, 0.98, f"subsampled to {MAX_SCATTER_POINTS} points", transform=ax1.transAxes, fontsize=8, verticalalignment="top")
    ax1.legend(loc="upper right")
    fig1.savefig(os.path.join(args.output_dir, "scatter_dose_vs_photons.png"), dpi=150)
    plt.close(fig1)

    # 主图：Cherenkov yield 线性拟合
    x_yield, y_yield = _subsample_scatter(dose_per_event, photons_per_event)
    fig_yield, ax_yield = plt.subplots()
    ax_yield.scatter(x_yield, y_yield, alpha=0.3, s=5, label="events")
    if slope_a is not None and intercept_b is not None:
        x_line = np.array([dose_per_event.min(), dose_per_event.max()])
        if np.ptp(x_line) == 0:
            x_line = np.array([0, dose_per_event.max() * 1.01])
        y_line = slope_a * x_line + intercept_b
        ax_yield.plot(x_line, y_line, "r-", linewidth=2, label="fit: N = a·E + b")
        leg_lines = [
            f"a (slope) = {slope_a:.4f} photons/MeV",
            f"b (intercept) = {intercept_b:.4f}",
            f"R² = {R2_fit:.4f}",
        ]
        if global_yield is not None:
            leg_lines.append(f"global yield (ΣN/ΣE) = {global_yield:.4f} photons/MeV")
        ax_yield.text(0.02, 0.98, "\n".join(leg_lines), transform=ax_yield.transAxes, fontsize=9, verticalalignment="top", family="monospace")
    ax_yield.set_xlabel("Dose per event (MeV)")
    ax_yield.set_ylabel("Photons per event")
    ax_yield.set_title("Cherenkov yield: photons vs dose (linear fit)")
    if n_ev > MAX_SCATTER_POINTS:
        ax_yield.text(0.02, 0.02, f"subsampled to {MAX_SCATTER_POINTS} points", transform=ax_yield.transAxes, fontsize=8)
    ax_yield.legend(loc="upper right")
    fig_yield.savefig(os.path.join(args.output_dir, "yield_fit_photons_vs_dose.png"), dpi=150)
    plt.close(fig_yield)

    # (2) Histogram photons
    fig2, ax2 = plt.subplots()
    ax2.hist(photons_per_event, bins=min(80, max(20, n_ev // 50)), edgecolor="k", alpha=0.7)
    ax2.set_xlabel("Photons per event")
    ax2.set_ylabel("Count")
    ax2.set_title("Histogram: photons per event")
    fig2.savefig(os.path.join(args.output_dir, "hist_photons_per_event.png"), dpi=150)
    plt.close(fig2)

    # (3) Histogram photons/dose（仅 dose >= dose_fit_threshold，再按分位数裁剪避免长尾）
    ratio_clip_q = getattr(args, "ratio_clip_quantile", 99.5)
    if np.any(mask_fit):
        ratio = np.where(mask_fit, photons_per_event / dose_per_event, np.nan)
        ratio = ratio[~np.isnan(ratio)]
        if len(ratio) > 0:
            clip_upper = np.nanpercentile(ratio, ratio_clip_q)
            ratio_clipped = np.clip(ratio, None, clip_upper)
            fig3, ax3 = plt.subplots()
            ax3.hist(ratio_clipped, bins=min(80, max(20, len(ratio_clipped) // 50)), edgecolor="k", alpha=0.7)
            ax3.set_xlabel("Photons per event / Dose per event (MeV)")
            ax3.set_ylabel("Count")
            ax3.set_title(f"Histogram: photons/dose (dose >= {dose_fit_threshold} MeV, ratio clipped at {ratio_clip_q}%)")
            fig3.savefig(os.path.join(args.output_dir, "hist_photons_over_dose.png"), dpi=150)
            plt.close(fig3)
        else:
            print("(No valid ratio values, skipping hist_photons_over_dose.png)")
    else:
        print(f"(No events with dose >= {dose_fit_threshold} MeV, skipping hist_photons_over_dose.png)")

    # 在图所在目录写入说明文件
    _write_figure_readme(args.output_dir)

    # ----- STEP 6: Electron-only (pdg == 11), same event mapping -----
    mask_elec = dose["pdg"] == 11
    if use_sparse:
        electron_dose_per_event = np.bincount(
            dose_compressed_idx[mask_elec],
            weights=dose["energy"][mask_elec],
            minlength=n_events_actual,
        )
    else:
        electron_dose_per_event = np.bincount(
            dose["event_id"][mask_elec],
            weights=dose["energy"][mask_elec],
            minlength=n_events,
        )

    std_elec = float(np.std(electron_dose_per_event, ddof=1)) if len(electron_dose_per_event) > 1 else 0.0
    if std_ph == 0 or std_elec == 0:
        print("电子剂量 vs 光子: 相关系数不可计算（零方差）")
        corr_electron_dose = None
    else:
        corr_electron_dose, _ = stats.pearsonr(photons_per_event, electron_dose_per_event)
        print("--- Electron dose (pdg==11) vs photons ---")
        print(f"corr_electron_dose (Pearson) = {corr_electron_dose:.6f}")

    print("--- Comparison ---")
    print(f"corr_total_dose   = {corr_pearson if corr_pearson is not None else 'N/A'}")
    print(f"corr_electron_dose = {corr_electron_dose if corr_electron_dose is not None else 'N/A'}")

    # 将统计与相关性结果写入 txt，与图同目录
    _write_stats_txt(
        args.output_dir,
        phsp_path=args.phsp,
        dose_path=args.dose,
        n_events=n_ev,
        nonzero_photon_events=nonzero_photon_events,
        nonzero_dose_events=nonzero_dose_events,
        mean_ph=mean_ph,
        std_ph=std_ph,
        mean_dose=mean_dose,
        std_dose=std_dose,
        global_yield=global_yield,
        slope_a=slope_a,
        intercept_b=intercept_b,
        R2_fit=R2_fit,
        corr_pearson=corr_pearson,
        p_pearson=p_pearson if corr_pearson is not None else None,
        corr_spearman=corr_spearman,
        p_spearman=p_spearman if corr_spearman is not None else None,
        corr_electron_dose=corr_electron_dose,
    )

    if use_sparse:
        assert electron_dose_per_event.shape == photons_per_event.shape, "electron shape must match photons in sparse branch"


if __name__ == "__main__":
    main()
