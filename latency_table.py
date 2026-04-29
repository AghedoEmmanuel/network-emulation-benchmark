import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu, ttest_ind

# =========================
# LOAD DATA
# =========================

mininet_latency = pd.read_csv("./result/mininet/mininet_raw_latency_time_results.csv")
seed_latency = pd.read_csv("./result/seed_ie/seed_ie_raw_latency_time_results.csv")

PAIR_COL = "pair"
ITER_COL = "iteration"
LAT_COL = "ping_rtt_ms"

mininet_latency = mininet_latency[[PAIR_COL, ITER_COL, LAT_COL]]
seed_latency = seed_latency[[PAIR_COL, ITER_COL, LAT_COL]]

mininet_latency[LAT_COL] = pd.to_numeric(mininet_latency[LAT_COL], errors="coerce")
seed_latency[LAT_COL] = pd.to_numeric(seed_latency[LAT_COL], errors="coerce")

mininet_latency = mininet_latency.dropna()
seed_latency = seed_latency.dropna()

# Standardise pair names
mininet_latency[PAIR_COL] = mininet_latency[PAIR_COL].astype(str).str.replace("_", "-", regex=False).str.upper()
seed_latency[PAIR_COL] = seed_latency[PAIR_COL].astype(str).str.replace("_", "-", regex=False).str.upper()

# If there are repeated samples per pair/iteration, keep them.
# This is better for latency distributions and statistical testing.

# =========================
# ROUTE ORDER AND HOPS
# =========================

ROUTE_ORDER = [
    "R1-R2",
    "R1-R3",
    "R1-R6",
    "R2-R5",
    "R3-R2",
    "R3-R6",
    "R4-R5",
    "R4-R6",
    "R6-R1"
]

HOPS = {
    "R1-R2": 1,
    "R1-R3": 2,
    "R1-R6": 1,
    "R2-R5": 2,
    "R3-R2": 1,
    "R3-R6": 2,
    "R4-R5": 1,
    "R4-R6": 2,
    "R6-R1": 1
}

# =========================
# CREATE LATENCY TABLE
# =========================

def create_latency_table(df, platform_name):
    results = []

    for pair in ROUTE_ORDER:
        data = df[df[PAIR_COL] == pair]
        lat = data[LAT_COL].dropna().values

        if len(lat) == 0:
            continue

        mean_latency = np.mean(lat)

        results.append({
            "Nodes": pair,
            "Hops": HOPS[pair],
            "Platform": platform_name,
            "Max (ms)": np.max(lat),
            "Min (ms)": np.min(lat),
            "Mean (ms)": mean_latency,
            "Std Dev (ms)": np.std(lat),
            "Median (ms)": np.median(lat),
            "Jitter (ms)": np.mean(np.abs(lat - mean_latency)),
            "Samples": len(lat)
        })

    return pd.DataFrame(results).round(2)


mininet_table = create_latency_table(mininet_latency, "Mininet")
seed_table = create_latency_table(seed_latency, "SEED IE")

combined_latency_table = pd.concat([mininet_table, seed_table], ignore_index=True)

print("\nMininet Latency Table:")
print(mininet_table)

print("\nSEED IE Latency Table:")
print(seed_table)

print("\nCombined Latency Table:")
print(combined_latency_table)

# Save tables
mininet_table.to_csv("./docs/tables/mininet_latency_table.csv", index=False)
seed_table.to_csv("./docs/tables/seed_ie_latency_table.csv", index=False)
combined_latency_table.to_csv("./docs/tables/combined_latency_table.csv", index=False)

# =========================
# CREATE JITTER TABLE
# =========================

jitter_rows = []

for pair in ROUTE_ORDER:
    m_row = mininet_table[mininet_table["Nodes"] == pair]
    s_row = seed_table[seed_table["Nodes"] == pair]

    if m_row.empty or s_row.empty:
        continue

    mininet_jitter = float(m_row["Jitter (ms)"].iloc[0])
    seed_jitter = float(s_row["Jitter (ms)"].iloc[0])

    jitter_rows.append({
        "Nodes": pair,
        "Hops": HOPS[pair],
        "Mininet Jitter (ms)": mininet_jitter,
        "SEED IE Jitter (ms)": seed_jitter,
        "Difference (Mininet - SEED IE)": round(mininet_jitter - seed_jitter, 2)
    })

jitter_table = pd.DataFrame(jitter_rows)

print("\nJitter Table:")
print(jitter_table)

jitter_table.to_csv("jitter_table.csv", index=False)

# =========================
# STATISTICAL TESTS FOR LATENCY
# =========================

def run_latency_stats(mininet_df, seed_df):
    results = []

    for pair in ROUTE_ORDER:
        m = mininet_df[mininet_df[PAIR_COL] == pair][LAT_COL].dropna().values
        s = seed_df[seed_df[PAIR_COL] == pair][LAT_COL].dropna().values

        if len(m) < 2 or len(s) < 2:
            continue

        # Mann-Whitney U test
        mw_stat, p_mw = mannwhitneyu(m, s, alternative="two-sided")

        # Welch's t-test
        t_stat, p_t = ttest_ind(m, s, equal_var=False)

        # Rank-biserial effect size
        n1 = len(m)
        n2 = len(s)

        # Direction: positive means SEED IE tends to have higher latency than Mininet
        r_rb = (2 * mw_stat) / (n1 * n2) - 1

        results.append({
            "Route": pair,
            "Mininet n": n1,
            "SEED IE n": n2,
            "Mininet Mean (ms)": np.mean(m),
            "SEED IE Mean (ms)": np.mean(s),
            "p (Mann-Whitney U)": p_mw,
            "p (Welch t-test)": p_t,
            "Effect Size (r_rb)": r_rb,
            "Interpretation": "Strong separation" if abs(r_rb) >= 0.5 else "Weak/Moderate separation"
        })

    return pd.DataFrame(results)


stats_table = run_latency_stats(mininet_latency, seed_latency)

stats_table = stats_table.round({
    "Mininet Mean (ms)": 4,
    "SEED IE Mean (ms)": 4,
    "p (Mann-Whitney U)": 6,
    "p (Welch t-test)": 6,
    "Effect Size (r_rb)": 4
})

print("\nLatency Statistical Comparison:")
print(stats_table)

stats_table.to_csv("./docs/tables/latency_statistical_comparison.csv", index=False)

# =========================
# BAR CHART: AVERAGE LATENCY
# =========================

latency_plot = combined_latency_table.pivot(
    index="Nodes",
    columns="Platform",
    values="Mean (ms)"
).reindex(ROUTE_ORDER)

x = np.arange(len(latency_plot.index))
width = 0.35

plt.figure(figsize=(12, 6))
plt.bar(x - width / 2, latency_plot["Mininet"], width, label="Mininet")
plt.bar(x + width / 2, latency_plot["SEED IE"], width, label="SEED IE")

plt.xlabel("Route Pair")
plt.ylabel("Average Latency (ms)")
plt.title("Average Latency Comparison between Mininet and SEED IE")
plt.xticks(x, latency_plot.index, rotation=45)
plt.legend()
plt.tight_layout()

plt.savefig("./docs/figures/latency_comparison_bar_chart.png", dpi=300)
plt.show()

# =========================
# BAR CHART: JITTER
# =========================

jitter_plot = jitter_table.set_index("Nodes").reindex(ROUTE_ORDER)

x = np.arange(len(jitter_plot.index))
width = 0.35

plt.figure(figsize=(12, 6))
plt.bar(x - width / 2, jitter_plot["Mininet Jitter (ms)"], width, label="Mininet")
plt.bar(x + width / 2, jitter_plot["SEED IE Jitter (ms)"], width, label="SEED IE")

plt.xlabel("Route Pair")
plt.ylabel("Jitter (ms)")
plt.title("Jitter Comparison between Mininet and SEED IE")
plt.xticks(x, jitter_plot.index, rotation=45)
plt.legend()
plt.tight_layout()

plt.savefig("jitter_comparison_bar_chart.png", dpi=300)
plt.show()