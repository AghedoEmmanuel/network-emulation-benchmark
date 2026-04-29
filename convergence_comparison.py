import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from scipy.stats import mannwhitneyu, ttest_ind

# =========================
# LOAD DATA
# =========================

mininet = pd.read_csv("./result/mininet/mininet_convergence_time_results.csv")
seed = pd.read_csv("./result/seed_ie/seed_ie_convergence_time_results.csv")

print(mininet.shape)
print(seed.shape)

print(mininet.head())
print(seed.head())


# =========================
# CREATE OUTPUT FOLDERS
# =========================

os.makedirs("./docs/tables", exist_ok=True)
os.makedirs("./docs/figures", exist_ok=True)


# =========================
# CLEAN NUMERIC COLUMNS
# =========================

for df in [mininet, seed]:
    df["failure_ms"] = pd.to_numeric(df["failure_ms"], errors="coerce")
    df["recovery_ms"] = pd.to_numeric(df["recovery_ms"], errors="coerce")

mininet = mininet.dropna(subset=["failure_ms", "recovery_ms"])
seed = seed.dropna(subset=["failure_ms", "recovery_ms"])


# =========================
# CONVERT TO LONG FORMAT
# =========================

mininet_long = pd.DataFrame({
    "Platform": ["Mininet"] * len(mininet) * 2,
    "Event": ["Failure"] * len(mininet) + ["Recovery"] * len(mininet),
    "Convergence_ms": list(mininet["failure_ms"]) + list(mininet["recovery_ms"])
})

seed_long = pd.DataFrame({
    "Platform": ["SEED IE"] * len(seed) * 2,
    "Event": ["Failure"] * len(seed) + ["Recovery"] * len(seed),
    "Convergence_ms": list(seed["failure_ms"]) + list(seed["recovery_ms"])
})

combined = pd.concat([mininet_long, seed_long], ignore_index=True)


# =========================
# TABLE 1: CONVERGENCE COMPARISON TABLE
# =========================

convergence_table = (
    combined
    .groupby(["Event", "Platform"])
    .agg(
        Samples=("Convergence_ms", "count"),
        Min_ms=("Convergence_ms", "min"),
        Max_ms=("Convergence_ms", "max"),
        Mean_ms=("Convergence_ms", "mean"),
        Median_ms=("Convergence_ms", "median"),
        Std_Dev_ms=("Convergence_ms", "std")
    )
    .reset_index()
    .round(3)
)

event_order = {"Failure": 1, "Recovery": 2}
platform_order = {"Mininet": 1, "SEED IE": 2}

convergence_table["event_order"] = convergence_table["Event"].map(event_order)
convergence_table["platform_order"] = convergence_table["Platform"].map(platform_order)

convergence_table = (
    convergence_table
    .sort_values(["event_order", "platform_order"])
    .drop(columns=["event_order", "platform_order"])
)

print("\nCONVERGENCE COMPARISON TABLE")
print(convergence_table)

convergence_table.to_csv(
    "./docs/tables/convergence_comparison_table.csv",
    index=False
)


# =========================
# TABLE 2: STATISTICAL SUMMARY
# =========================

def format_p(p):
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"

def interpret_effect(r):
    if abs(r) >= 0.8:
        return "Strong distributional separation"
    elif abs(r) >= 0.5:
        return "Moderate distributional separation"
    else:
        return "Weak distributional separation"

def rank_biserial(x, y):
    u_stat, p_mw = mannwhitneyu(x, y, alternative="two-sided")
    n1 = len(x)
    n2 = len(y)
    r_rb = (2 * u_stat) / (n1 * n2) - 1
    return u_stat, p_mw, r_rb

stats_rows = []

for event, mininet_col, seed_col in [
    ("Failure convergence", "failure_ms", "failure_ms"),
    ("Recovery convergence", "recovery_ms", "recovery_ms")
]:
    mininet_vals = mininet[mininet_col].dropna()
    seed_vals = seed[seed_col].dropna()

    u_stat, p_mw, r_rb = rank_biserial(mininet_vals, seed_vals)

    t_stat, p_t = ttest_ind(
        mininet_vals,
        seed_vals,
        equal_var=False
    )

    stats_rows.append({
        "Metric": event,
        "p (Mann–Whitney)": format_p(p_mw),
        "p (Welch t-test)": format_p(p_t),
        "Effect Size (r_rb)": round(r_rb, 3),
        "Interpretation": interpret_effect(r_rb)
    })

stats_table = pd.DataFrame(stats_rows)

print("\nCONVERGENCE STATISTICAL SUMMARY")
print(stats_table)

stats_table.to_csv(
    "./docs/tables/convergence_statistical_summary.csv",
    index=False
)


# =========================
# BAR CHART: MEAN CONVERGENCE TIME
# =========================

plot_data = convergence_table.pivot(
    index="Event",
    columns="Platform",
    values="Mean_ms"
).loc[["Failure", "Recovery"]]

plot_data.plot(kind="bar", figsize=(8, 5))

plt.xlabel("Convergence Event")
plt.ylabel("Mean Convergence Time (ms)")
plt.title("Mean Convergence Time Comparison")
plt.xticks(rotation=0)
plt.tight_layout()

plt.savefig(
    "./docs/figures/convergence_mean_bar_chart.png",
    dpi=300
)

plt.show()


# =========================
# BOX PLOT: DISTRIBUTION COMPARISON
# =========================

box_data = [
    mininet["failure_ms"],
    seed["failure_ms"],
    mininet["recovery_ms"],
    seed["recovery_ms"]
]

box_labels = [
    "Mininet\nFailure",
    "SEED IE\nFailure",
    "Mininet\nRecovery",
    "SEED IE\nRecovery"
]

plt.figure(figsize=(9, 5))
plt.boxplot(box_data, labels=box_labels)

plt.ylabel("Convergence Time (ms)")
plt.title("Convergence Time Distribution Comparison")
plt.tight_layout()

plt.savefig(
    "./docs/figures/convergence_box_plot.png",
    dpi=300
)

plt.show()