import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.stats import mannwhitneyu, ttest_ind
import os
import warnings
warnings.filterwarnings('ignore')


# ── Load datasets ─────────────────────────────────────────────────────────────
ospf = pd.read_csv('./results/ospf_benchmark_results_iterative_ms.csv')
sdn  = pd.read_csv('./results/sdn_benchmark_results_iterative_ms.csv')

print(f"OSPF iterations: {len(ospf)}   SDN iterations: {len(sdn)}")

FIG_DIR = "./docs/tables"
os.makedirs(FIG_DIR, exist_ok=True)


# ── Helper: full descriptive stats ───────────────────────────────────────────
def stats(series):
    s = series.dropna()
    return {
        "n":      len(s),
        "mean":   s.mean(),
        "median": s.median(),
        "std":    s.std(),
        "min":    s.min(),
        "max":    s.max(),
    }


# ── Helper: both statistical tests with rank-biserial effect size ─────────────
def run_tests(a, b):
    a = a.dropna()
    b = b.dropna()

    # Mann-Whitney U (non-parametric)
    try:
        u_stat, p_mw = mannwhitneyu(a, b, alternative='two-sided')
        # Rank-biserial correlation: r = 1 - (2U)/(n1*n2)
        r_rb = 1 - (2 * u_stat) / (len(a) * len(b))
        p_mw_str = f"{p_mw:.4f}" if p_mw >= 0.0001 else "<0.0001"
        r_rb_str = f"{r_rb:.3f}"
    except Exception:
        p_mw_str = "N/A"
        r_rb_str = "N/A"

    # Welch's t-test (parametric, unequal variances)
    try:
        _, p_t = ttest_ind(a, b, equal_var=False)
        p_t_str = f"{p_t:.4f}" if p_t >= 0.0001 else "<0.0001"
    except Exception:
        p_t_str = "N/A"

    return p_mw_str, p_t_str, r_rb_str


# ══════════════════════════════════════════════════════════════════════════════
# TABLE 1 — Latency (avg_ms) across three route pairs
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("TABLE 1: LATENCY (avg ms) – per route pair")
print("=" * 90)

lat_rows = []
for ospf_col, sdn_col_suffix, label in [
    ("latency_r1_r2_avg_ms", "h1_h2", "Adjacent (1-hop)"),
    ("latency_r1_r4_avg_ms", "h1_h4", "Opposite (3-hop)"),
    ("latency_r1_r6_avg_ms", "h1_h6", "Adjacent alt (1-hop)"),
]:
    sdn_col = f"latency_{sdn_col_suffix}_avg_ms"
    o = stats(ospf[ospf_col])
    s = stats(sdn[sdn_col])
    p_mw, p_t, r_rb = run_tests(ospf[ospf_col], sdn[sdn_col])
    lat_rows.append({
        "Route Pair":          label,
        "OSPF Mean (ms)":      f"{o['mean']:.4f}",
        "OSPF Median (ms)":    f"{o['median']:.4f}",
        "OSPF Min (ms)":       f"{o['min']:.4f}",
        "OSPF Max (ms)":       f"{o['max']:.4f}",
        "OSPF Std":            f"{o['std']:.4f}",
        "SDN Mean (ms)":       f"{s['mean']:.4f}",
        "SDN Median (ms)":     f"{s['median']:.4f}",
        "SDN Min (ms)":        f"{s['min']:.4f}",
        "SDN Max (ms)":        f"{s['max']:.4f}",
        "SDN Std":             f"{s['std']:.4f}",
        "p (Mann-Whitney)":    p_mw,
        "p (Welch t-test)":    p_t,
        "Effect Size (r_rb)":  r_rb,
    })

print(pd.DataFrame(lat_rows).to_string(index=False))


# ══════════════════════════════════════════════════════════════════════════════
# TABLE 2 — Jitter (ms) across three route pairs
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("TABLE 2: JITTER (ms) – per route pair")
print("=" * 90)

jit_rows = []
for ospf_col, sdn_col, label in [
    ("jitter_r1_r2_ms", "jitter_h1_h2_ms", "Adjacent (1-hop)"),
    ("jitter_r1_r4_ms", "jitter_h1_h4_ms", "Opposite (3-hop)"),
    ("jitter_r1_r6_ms", "jitter_h1_h6_ms", "Adjacent alt (1-hop)"),
]:
    o = stats(ospf[ospf_col])
    s = stats(sdn[sdn_col])
    p_mw, p_t, r_rb = run_tests(ospf[ospf_col], sdn[sdn_col])
    jit_rows.append({
        "Route Pair":          label,
        "OSPF Mean (ms)":      f"{o['mean']:.5f}",
        "OSPF Median (ms)":    f"{o['median']:.5f}",
        "OSPF Min (ms)":       f"{o['min']:.5f}",
        "OSPF Max (ms)":       f"{o['max']:.5f}",
        "OSPF Std":            f"{o['std']:.5f}",
        "SDN Mean (ms)":       f"{s['mean']:.5f}",
        "SDN Median (ms)":     f"{s['median']:.5f}",
        "SDN Min (ms)":        f"{s['min']:.5f}",
        "SDN Max (ms)":        f"{s['max']:.5f}",
        "SDN Std":             f"{s['std']:.5f}",
        "p (Mann-Whitney)":    p_mw,
        "p (Welch t-test)":    p_t,
        "Effect Size (r_rb)":  r_rb,
    })

print(pd.DataFrame(jit_rows).to_string(index=False))


# ══════════════════════════════════════════════════════════════════════════════
# TABLE 3 — Throughput (Mbps) per route pair
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("TABLE 3: THROUGHPUT (Mbps) – per route pair")
print("=" * 90)

tput_rows = []
for ospf_col, sdn_col, label in [
    ("throughput_r1_r2_mbps", "throughput_h1_h2_mbps", "1-hop pair"),
    ("throughput_r1_r4_mbps", "throughput_h1_h4_mbps", "3-hop pair"),
    # ("throughput_r1_r6_mbps", "throughput_h1_h6_mbps", "Adjacent alt (1-hop)"),
]:
    o = stats(ospf[ospf_col])
    s = stats(sdn[sdn_col])
    p_mw, p_t, r_rb = run_tests(ospf[ospf_col], sdn[sdn_col])
    tput_rows.append({
        "Route Pair":          label,
        "OSPF Mean (Mbps)":    f"{o['mean']:.2f}",
        "OSPF Median (Mbps)":  f"{o['median']:.2f}",
        "OSPF Min (Mbps)":     f"{o['min']:.2f}",
        "OSPF Max (Mbps)":     f"{o['max']:.2f}",
        "OSPF Std":            f"{o['std']:.2f}",
        "SDN Mean (Mbps)":     f"{s['mean']:.2f}",
        "SDN Median (Mbps)":   f"{s['median']:.2f}",
        "SDN Min (Mbps)":      f"{s['min']:.2f}",
        "SDN Max (Mbps)":      f"{s['max']:.2f}",
        "SDN Std":             f"{s['std']:.2f}",
        "p (Mann-Whitney)":    p_mw,
        "p (Welch t-test)":    p_t,
        "Effect Size (r_rb)":  r_rb,
    })

print(pd.DataFrame(tput_rows).to_string(index=False))


# ══════════════════════════════════════════════════════════════════════════════
# TABLE 3b — Bandwidth (Mbps) per route pair
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("TABLE 3b: BANDWIDTH (Mbps) – per route pair")
print("=" * 90)

bw_rows = []
for ospf_col, sdn_col, label in [
    ("bandwidth_r1_r2_mbps", "bandwidth_h1_h2_mbps", "1-hop pair"),
    ("bandwidth_r1_r4_mbps", "bandwidth_h1_h4_mbps", "3-hop pair"),
    # ("bandwidth_r1_r6_mbps", "bandwidth_h1_h6_mbps", "Adjacent alt (1-hop)"),
]:
    o = stats(ospf[ospf_col])
    s = stats(sdn[sdn_col])
    p_mw, p_t, r_rb = run_tests(ospf[ospf_col], sdn[sdn_col])
    bw_rows.append({
        "Route Pair":          label,
        "OSPF Mean (Mbps)":    f"{o['mean']:.2f}",
        "OSPF Median (Mbps)":  f"{o['median']:.2f}",
        "OSPF Min (Mbps)":     f"{o['min']:.2f}",
        "OSPF Max (Mbps)":     f"{o['max']:.2f}",
        "OSPF Std":            f"{o['std']:.2f}",
        "SDN Mean (Mbps)":     f"{s['mean']:.2f}",
        "SDN Median (Mbps)":   f"{s['median']:.2f}",
        "SDN Min (Mbps)":      f"{s['min']:.2f}",
        "SDN Max (Mbps)":      f"{s['max']:.2f}",
        "SDN Std":             f"{s['std']:.2f}",
        "p (Mann-Whitney)":    p_mw,
        "p (Welch t-test)":    p_t,
        "Effect Size (r_rb)":  r_rb,
    })

print(pd.DataFrame(bw_rows).to_string(index=False))


# ══════════════════════════════════════════════════════════════════════════════
# TABLE 4 — CPU & Memory utilisation
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 90)
print("TABLE 4: RESOURCE UTILISATION")
print("=" * 90)

res_rows = []
for col, label in [
    ("cpu_total_busy_pct", "CPU Total Busy (%)"),
    ("mem_utilisation_pct", "Memory Utilisation (%)"),
    ("mem_used_mb",         "Memory Used (MB)"),
]:
    o = stats(ospf[col])
    s = stats(sdn[col])
    p_mw, p_t, r_rb = run_tests(ospf[col], sdn[col])
    res_rows.append({
        "Metric":              label,
        "OSPF Mean":           f"{o['mean']:.3f}",
        "OSPF Median":         f"{o['median']:.3f}",
        "OSPF Min":            f"{o['min']:.3f}",
        "OSPF Max":            f"{o['max']:.3f}",
        "OSPF Std":            f"{o['std']:.3f}",
        "SDN Mean":            f"{s['mean']:.3f}",
        "SDN Median":          f"{s['median']:.3f}",
        "SDN Min":             f"{s['min']:.3f}",
        "SDN Max":             f"{s['max']:.3f}",
        "SDN Std":             f"{s['std']:.3f}",
        "p (Mann-Whitney)":    p_mw,
        "p (Welch t-test)":    p_t,
        "Effect Size (r_rb)":  r_rb,
    })

print(pd.DataFrame(res_rows).to_string(index=False))


# ══════════════════════════════════════════════════════════════════════════════
# FIGURES
# ══════════════════════════════════════════════════════════════════════════════
COLORS = {"OSPF (SEED IE)": "#2166ac", "SDN (Mininet)": "#d6604d"}


def styled_box(ax, data_dict, ylabel, title, log=False):
    labels = list(data_dict.keys())
    vals   = [data_dict[k] for k in labels]
    bp = ax.boxplot(vals, patch_artist=True, widths=0.4,
                    medianprops=dict(color='black', linewidth=2))
    palette = list(COLORS.values())
    for patch, color in zip(bp['boxes'], palette):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight='bold')
    if log:
        ax.set_yscale('log')
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.spines[['top', 'right']].set_visible(False)


# Figure 1: Latency boxplot (log scale, all three pairs)
fig, axes = plt.subplots(1, 3, figsize=(13, 5))
fig.suptitle("Figure 1: Latency Comparison – Mininet (SDN) vs SEED IE (OSPF)", fontsize=12, y=1.01)

for ax, (oc, sc, title) in zip(axes, [
    ("latency_r1_r2_avg_ms", "latency_h1_h2_avg_ms", "Adjacent 1-hop\n(r1–r2 / h1–h2)"),
    ("latency_r1_r4_avg_ms", "latency_h1_h4_avg_ms", "Multi-hop\n(r1–r4 / h1–h4)"),
    ("latency_r1_r6_avg_ms", "latency_h1_h6_avg_ms", "Adjacent alt\n(r1–r6 / h1–h6)"),
]):
    styled_box(ax,
               {"OSPF (SEED IE)": ospf[oc].dropna().values,
                "SDN (Mininet)":  sdn[sc].dropna().values},
               "Average Latency (ms)", title, log=True)

plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "fig1_latency_boxplot.png"), dpi=200, bbox_inches='tight')
plt.close()
print("\n✓ Saved fig1_latency_boxplot.png")

# Figure 2: Throughput boxplot
fig, axes = plt.subplots(1, 2, figsize=(10, 5))
fig.suptitle("Figure 2: Throughput Comparison – Mininet (SDN) vs SEED IE (OSPF)", fontsize=12)

for ax, (oc, sc, title) in zip(axes, [
    ("throughput_r1_r2_mbps", "throughput_h1_h2_mbps", "1-hop pair"),
    ("throughput_r1_r4_mbps", "throughput_h1_h4_mbps", "3-hop pair"),
    ("throughput_r1_r6_mbps", "throughput_h1_h6_mbps", "Adjacent alt (1-hop)"),
]):
    styled_box(ax,
               {"OSPF (SEED IE)": ospf[oc].dropna().values,
                "SDN (Mininet)":  sdn[sc].dropna().values},
               "Throughput (Mbps)", title)

plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "fig2_throughput_boxplot.png"), dpi=200, bbox_inches='tight')
plt.close()
print("✓ Saved fig2_throughput_boxplot.png")

# Figure 3: Jitter boxplot (log scale)
fig, axes = plt.subplots(1, 3, figsize=(13, 5))
fig.suptitle("Figure 3: Jitter Comparison – Mininet (SDN) vs SEED IE (OSPF)", fontsize=12)

for ax, (oc, sc, title) in zip(axes, [
    ("jitter_r1_r2_ms", "jitter_h1_h2_ms", "Adjacent 1-hop"),
    ("jitter_r1_r4_ms", "jitter_h1_h4_ms", "Multi-hop"),
    ("jitter_r1_r6_ms", "jitter_h1_h6_ms", "Adjacent alt"),
]):
    styled_box(ax,
               {"OSPF (SEED IE)": ospf[oc].dropna().values,
                "SDN (Mininet)":  sdn[sc].dropna().values},
               "Jitter (ms)", title, log=True)

plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "fig3_jitter_boxplot.png"), dpi=200, bbox_inches='tight')
plt.close()
print("✓ Saved fig3_jitter_boxplot.png")

# Figure 4: CPU & Memory utilisation
fig, axes = plt.subplots(1, 2, figsize=(10, 5))
fig.suptitle("Figure 4: Resource Utilisation – Mininet (SDN) vs SEED IE (OSPF)", fontsize=12)

styled_box(axes[0],
           {"OSPF (SEED IE)": ospf["cpu_total_busy_pct"].dropna().values,
            "SDN (Mininet)":  sdn["cpu_total_busy_pct"].dropna().values},
           "CPU Utilisation (%)", "CPU Total Busy")

styled_box(axes[1],
           {"OSPF (SEED IE)": ospf["mem_utilisation_pct"].dropna().values,
            "SDN (Mininet)":  sdn["mem_utilisation_pct"].dropna().values},
           "Memory Utilisation (%)", "Memory")

plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "fig4_resource_boxplot.png"), dpi=200, bbox_inches='tight')
plt.close()
print("✓ Saved fig4_resource_boxplot.png")

# Figure 5: OSPF latency stability time-series
fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(ospf["iteration"], ospf["latency_r1_r2_avg_ms"], alpha=0.6, linewidth=0.7,
        color=COLORS["OSPF (SEED IE)"], label="r1–r2")
ax.plot(ospf["iteration"], ospf["latency_r1_r4_avg_ms"], alpha=0.6, linewidth=0.7,
        color="#4dac26", label="r1–r4")
ax.set_xlabel("Iteration")
ax.set_ylabel("Average Latency (ms)")
ax.set_title("Figure 5: OSPF Latency Stability Over 1,000 Iterations", fontweight='bold')
ax.legend()
ax.spines[['top', 'right']].set_visible(False)
ax.grid(axis='y', linestyle='--', alpha=0.4)
plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "fig5_ospf_stability.png"), dpi=200, bbox_inches='tight')
plt.close()
print("✓ Saved fig5_ospf_stability.png")

# Figure 6: Bandwidth boxplot
fig, axes = plt.subplots(1, 2, figsize=(10, 5))
fig.suptitle("Figure 6: Bandwidth Comparison – Mininet (SDN) vs SEED IE (OSPF)", fontsize=12)

for ax, (oc, sc, title) in zip(axes, [
    ("bandwidth_r1_r2_mbps", "bandwidth_h1_h2_mbps", "1-hop pair"),
    ("bandwidth_r1_r4_mbps", "bandwidth_h1_h4_mbps", "3-hop pair"),
    ("bandwidth_r1_r6_mbps", "bandwidth_h1_h6_mbps", "Adjacent alt (1-hop)"),
]):
    styled_box(ax,
               {"OSPF (SEED IE)": ospf[oc].dropna().values,
                "SDN (Mininet)":  sdn[sc].dropna().values},
               "Bandwidth (Mbps)", title)

plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "fig6_bandwidth_boxplot.png"), dpi=200, bbox_inches='tight')
plt.close()
print("✓ Saved fig6_bandwidth_boxplot.png")

print("\n✅ All analysis complete.")