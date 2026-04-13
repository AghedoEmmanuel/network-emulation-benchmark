"""
Convergence Comparison: SDN (POX/OpenFlow) vs OSPF (FRRouting)
Dissertation: Comparative Performance Evaluation of Network Emulation Platforms
"""
 
import csv
import statistics
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os

# ── Data loading ──────────────────────────────────────────────────────────────
 
def load_csv(path):
    failure_ms, recovery_ms = [], []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            failure_ms.append(float(row["failure_ms"]))
            recovery_ms.append(float(row["recovery_ms"]))
    return failure_ms, recovery_ms
 
 
SDN_PATH  = "./results/sdn_benchmark_results_iterative_ms_convergence.csv"
OSPF_PATH = "./results/ospf_benchmark_results_iterative_ms_convergence.csv"
 
sdn_fail,  sdn_rec  = load_csv(SDN_PATH)
ospf_fail, ospf_rec = load_csv(OSPF_PATH)

# ── Descriptive statistics ────────────────────────────────────────────────────
 
def describe(data, label):
    return {
        "label":  label,
        "n":      len(data),
        "mean":   statistics.mean(data),
        "median": statistics.median(data),
        "stdev":  statistics.stdev(data),
        "min":    min(data),
        "max":    max(data),
        "q1":     float(np.percentile(data, 25)),
        "q3":     float(np.percentile(data, 75)),
    }
 
groups = {
    "SDN Failure":   sdn_fail,
    "SDN Recovery":  sdn_rec,
    "OSPF Failure":  ospf_fail,
    "OSPF Recovery": ospf_rec,
}
 
print("=" * 65)
print(f"{'Metric':<20} {'Mean':>8} {'Median':>8} {'StDev':>8} {'Min':>8} {'Max':>8}")
print("=" * 65)
for name, data in groups.items():
    d = describe(data, name)
    print(f"{name:<20} {d['mean']:>8.2f} {d['median']:>8.2f} "
          f"{d['stdev']:>8.2f} {d['min']:>8.2f} {d['max']:>8.2f}")
print()
 
# ── Outlier identification (> mean + 2*stdev) ─────────────────────────────────
 
print("Outlier check (> mean + 2 SD):")
for name, data in groups.items():
    m, s = statistics.mean(data), statistics.stdev(data)
    threshold = m + 2 * s
    outliers = [(i + 1, v) for i, v in enumerate(data) if v > threshold]
    if outliers:
        print(f"  {name}: {outliers}")
    else:
        print(f"  {name}: none")
print()
 
# ── Mann-Whitney U tests ──────────────────────────────────────────────────────
 
mw_fail = stats.mannwhitneyu(sdn_fail, ospf_fail, alternative="two-sided")
mw_rec  = stats.mannwhitneyu(sdn_rec,  ospf_rec,  alternative="two-sided")
 
print("Mann-Whitney U tests (two-sided):")
print(f"  Failure convergence : U={mw_fail.statistic:.1f}, p={mw_fail.pvalue:.2e}")
print(f"  Recovery convergence: U={mw_rec.statistic:.1f},  p={mw_rec.pvalue:.2e}")
print()
 
# ── Effect size (rank-biserial correlation) ───────────────────────────────────
 
def rank_biserial(u, n1, n2):
    return 1 - (2 * u) / (n1 * n2)
 
n = len(sdn_fail)
rb_fail = rank_biserial(mw_fail.statistic, n, n)
rb_rec  = rank_biserial(mw_rec.statistic,  n, n)
print(f"Rank-biserial effect size:")
print(f"  Failure : r = {rb_fail:.3f}")
print(f"  Recovery: r = {rb_rec:.3f}")
print()
 
# ── Plots ─────────────────────────────────────────────────────────────────────
 
SDN_COLOUR  = "#2563eb"   # blue
OSPF_COLOUR = "#dc2626"   # red
ALPHA       = 0.85
 
fig, axes = plt.subplots(1, 3, figsize=(16, 6))
fig.suptitle(
    "Convergence Comparison: SDN (POX/OpenFlow 1.0) vs OSPF (FRRouting)",
    fontsize=13, fontweight="bold", y=1.01
)
 
iterations = list(range(1, n + 1))
 
# ── Plot 1: Failure convergence over iterations ───────────────────────────────
ax1 = axes[0]
ax1.plot(iterations, sdn_fail,  color=SDN_COLOUR,  linewidth=1.2,
         label="SDN failure",  alpha=ALPHA)
ax1.plot(iterations, ospf_fail, color=OSPF_COLOUR, linewidth=1.2,
         label="OSPF failure", alpha=ALPHA)
ax1.axhline(statistics.mean(sdn_fail),  color=SDN_COLOUR,
            linestyle="--", linewidth=1.0, alpha=0.6)
ax1.axhline(statistics.mean(ospf_fail), color=OSPF_COLOUR,
            linestyle="--", linewidth=1.0, alpha=0.6)
ax1.set_title("Failure Convergence per Iteration")
ax1.set_xlabel("Iteration")
ax1.set_ylabel("Time (ms)")
ax1.legend(fontsize=9)
ax1.grid(True, alpha=0.3)
 
# ── Plot 2: Recovery convergence over iterations ──────────────────────────────
ax2 = axes[1]
ax2.plot(iterations, sdn_rec,  color=SDN_COLOUR,  linewidth=1.2,
         label="SDN recovery",  alpha=ALPHA)
ax2.plot(iterations, ospf_rec, color=OSPF_COLOUR, linewidth=1.2,
         label="OSPF recovery", alpha=ALPHA)
ax2.axhline(statistics.mean(sdn_rec),  color=SDN_COLOUR,
            linestyle="--", linewidth=1.0, alpha=0.6)
ax2.axhline(statistics.mean(ospf_rec), color=OSPF_COLOUR,
            linestyle="--", linewidth=1.0, alpha=0.6)
ax2.set_title("Recovery Convergence per Iteration")
ax2.set_xlabel("Iteration")
ax2.set_ylabel("Time (ms)")
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)
 
# ── Plot 3: Box plots for all four groups ─────────────────────────────────────
ax3 = axes[2]
bp_data   = [sdn_fail, sdn_rec, ospf_fail, ospf_rec]
bp_labels = ["SDN\nFailure", "SDN\nRecovery", "OSPF\nFailure", "OSPF\nRecovery"]
bp_colours = [SDN_COLOUR, SDN_COLOUR, OSPF_COLOUR, OSPF_COLOUR]
 
bp = ax3.boxplot(bp_data, patch_artist=True, notch=False,
                 medianprops=dict(color="white", linewidth=2))
for patch, colour in zip(bp["boxes"], bp_colours):
    patch.set_facecolor(colour)
    patch.set_alpha(0.7)
 
ax3.set_xticklabels(bp_labels, fontsize=9)
ax3.set_title("Distribution Comparison (Box Plot)")
ax3.set_ylabel("Time (ms)")
ax3.grid(True, axis="y", alpha=0.3)
 
sdn_patch  = mpatches.Patch(color=SDN_COLOUR,  alpha=0.7, label="SDN")
ospf_patch = mpatches.Patch(color=OSPF_COLOUR, alpha=0.7, label="OSPF")
ax3.legend(handles=[sdn_patch, ospf_patch], fontsize=9)
 
plt.tight_layout()
out_path = "convergence_comparison.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"Plot saved to: {out_path}")
plt.close()