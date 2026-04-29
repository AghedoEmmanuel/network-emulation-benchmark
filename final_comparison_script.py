import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu, ttest_ind

# =========================
# FILE PATHS
# =========================

seed_bandwidth_file = "./docs/tables/seed_ie_bandwidth_route_summary.csv"
seed_throughput_file = "./docs/tables/seed_ie_throughput_route_summary.csv"
seed_resource_file = "./docs/tables/seed_ie_resource_overhead_route_summary.csv"

mininet_bandwidth_file = "./docs/tables/mininet_bandwidth_route_summary.csv"
mininet_throughput_file = "./docs/tables/mininet_throughput_route_summary.csv"
mininet_resource_file = "./docs/tables/mininet_resource_overhead_route_summary.csv"

seed_raw_file = "./docs/tables/ospf_benchmark_results_iterative_ms.csv"
mininet_raw_file = "./docs/tables/mininet_throughput_bandwidth_cpu_memory_raw.csv"


# =========================
# LOAD SAVED SUMMARY TABLES
# =========================

seed_bw = pd.read_csv(seed_bandwidth_file)
seed_tp = pd.read_csv(seed_throughput_file)
seed_res = pd.read_csv(seed_resource_file)

mininet_bw = pd.read_csv(mininet_bandwidth_file)
mininet_tp = pd.read_csv(mininet_throughput_file)
mininet_res = pd.read_csv(mininet_resource_file)


# =========================
# HOP MAP
# =========================

hop_map = {
    "R1-R2": 1,
    "R1-R3": 2,
    "R3-R2": 1,
    "R3-R6": 2,
    "R1-R6": 1,
    "R2-R5": 2,
    "R4-R5": 1,
    "R4-R6": 2,
    "R6-R1": 1
}


# =========================
# FORMAT COMPARISON TABLE FUNCTION
# =========================

def build_comparison_table(seed_table, mininet_table, metric):
    seed_table = seed_table.copy()
    mininet_table = mininet_table.copy()

    seed_table["Platform"] = "SEED IE"
    mininet_table["Platform"] = "Mininet"

    if metric == "Bandwidth":
        cols = {
            "Min_Bandwidth_Mbps": "Min",
            "Max_Bandwidth_Mbps": "Max",
            "Mean_Bandwidth_Mbps": "Mean",
            "Median_Bandwidth_Mbps": "Median",
            "Std_Bandwidth_Mbps": "Std Dev"
        }

    elif metric == "Throughput":
        cols = {
            "Min_Throughput_Mbps": "Min",
            "Max_Throughput_Mbps": "Max",
            "Mean_Throughput_Mbps": "Mean",
            "Median_Throughput_Mbps": "Median",
            "Std_Throughput_Mbps": "Std Dev"
        }

    elif metric == "CPU":
        cols = {
            "Min_CPU_Percent": "Min",
            "Max_CPU_Percent": "Max",
            "Mean_CPU_Percent": "Mean",
            "Median_CPU_Percent": "Median",
            "Std_CPU_Percent": "Std Dev"
        }

    elif metric == "Memory":
        cols = {
            "Min_Memory_Percent": "Min",
            "Max_Memory_Percent": "Max",
            "Mean_Memory_Percent": "Mean",
            "Median_Memory_Percent": "Median",
            "Std_Memory_Percent": "Std Dev"
        }

    else:
        raise ValueError("Metric must be Bandwidth, Throughput, CPU, or Memory")

    combined_table = pd.concat([mininet_table, seed_table], ignore_index=True)

    combined_table["Hops"] = combined_table["Nodes"].map(hop_map)

    final_table = combined_table[
        ["Nodes", "Hops", "Platform"] + list(cols.keys())
    ].rename(columns=cols)

    final_table["route_order"] = final_table["Nodes"].map(
        {route: i for i, route in enumerate(hop_map.keys())}
    )

    final_table["platform_order"] = final_table["Platform"].map({
        "Mininet": 1,
        "SEED IE": 2
    })

    final_table = (
        final_table
        .sort_values(["route_order", "platform_order"])
        .drop(columns=["route_order", "platform_order"])
        .round(3)
    )

    return final_table


# =========================
# FINAL COMPARISON TABLES
# =========================

bandwidth_comparison = build_comparison_table(seed_bw, mininet_bw, "Bandwidth")
throughput_comparison = build_comparison_table(seed_tp, mininet_tp, "Throughput")
cpu_comparison = build_comparison_table(seed_res, mininet_res, "CPU")
memory_comparison = build_comparison_table(seed_res, mininet_res, "Memory")

print("\nBANDWIDTH COMPARISON TABLE")
print(bandwidth_comparison)

print("\nTHROUGHPUT COMPARISON TABLE")
print(throughput_comparison)

print("\nCPU RESOURCE OVERHEAD COMPARISON TABLE")
print(cpu_comparison)

print("\nMEMORY RESOURCE OVERHEAD COMPARISON TABLE")
print(memory_comparison)


# =========================
# SAVE FINAL COMPARISON TABLES
# =========================

bandwidth_comparison.to_csv("./docs/tables/bandwidth_comparison_table.csv", index=False)
throughput_comparison.to_csv("./docs/tables/throughput_comparison_table.csv", index=False)
cpu_comparison.to_csv("./docs/tables/cpu_resource_comparison_table.csv", index=False)
memory_comparison.to_csv("./docs/tables/memory_resource_comparison_table.csv", index=False)


# =========================
# BAR CHART FUNCTION
# =========================

def plot_comparison(comparison_table, metric_name, ylabel,filename):
    plot_data = comparison_table.pivot(
        index="Nodes",
        columns="Platform",
        values="Mean"
    )

    plot_data = plot_data.loc[list(hop_map.keys())]

    plot_data.plot(kind="bar", figsize=(10, 5))

    plt.xlabel("Route")
    plt.ylabel(ylabel)
    plt.title(f"{metric_name} Comparison: Mininet vs SEED IE")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f"./docs/figures/{filename}.png", dpi=300)
    plt.show()


plot_comparison(
    bandwidth_comparison,
    "Bandwidth",
    "Mean Bandwidth (Mbps)",
    "bandwidth_comparison"
)

plot_comparison(
    throughput_comparison,
    "Throughput",
    "Mean Throughput (Mbps)",
    "throughput_comparison"
)

plot_comparison(
    cpu_comparison,
    "CPU Resource Overhead",
    "Mean CPU Utilisation (%)",
    "cpu_comparison"
)

plot_comparison(
    memory_comparison,
    "Memory Resource Overhead",
    "Mean Memory Utilisation (%)",
    "memory_comparison"
)


# ============================================================
# STATISTICAL TESTS
# IMPORTANT:
# These must use raw values, not the saved summary tables.
# ============================================================

# =========================
# REBUILD SEED LONG RAW DATA
# =========================

seed_raw = pd.read_csv(seed_raw_file)

pairs = [
    "r1_r2",
    "r1_r3",
    "r3_r2",
    "r3_r6",
    "r1_r6",
    "r2_r5",
    "r4_r5",
    "r4_r6",
    "r6_r1"
]

seed_rows = []

for _, row in seed_raw.iterrows():
    for pair in pairs:
        seed_rows.append({
            "Nodes": pair.replace("_", "-").upper(),
            "Platform": "SEED IE",
            "bandwidth_mbps": row[f"bandwidth_{pair}_mbps"],
            "throughput_mbps": row[f"throughput_{pair}_mbps"],
            "cpu_percent": row["cpu_total_busy_pct"],
            "memory_percent": row["mem_utilisation_pct"]
        })

seed_long = pd.DataFrame(seed_rows)


# =========================
# REBUILD MININET LONG RAW DATA
# =========================

mininet_raw = pd.read_csv(mininet_raw_file)

mininet_raw["success_clean"] = (
    mininet_raw["success"]
    .astype(str)
    .str.lower()
    .str.strip()
)

mininet_raw = mininet_raw[
    mininet_raw["success_clean"].isin(["true", "1", "yes"])
].copy()

mininet_raw["pair"] = mininet_raw["pair"].astype(str).str.strip()
mininet_raw["Nodes"] = mininet_raw["pair"].str.replace("_", "-", regex=False).str.upper()
mininet_raw["Platform"] = "Mininet"

numeric_cols = [
    "bandwidth_bps",
    "throughput_bps",
    "cpu_percent",
    "memory_after_percent"
]

for col in numeric_cols:
    mininet_raw[col] = pd.to_numeric(mininet_raw[col], errors="coerce")

mininet_raw = mininet_raw.dropna(subset=numeric_cols)

mininet_raw["bandwidth_mbps"] = mininet_raw["bandwidth_bps"] / 1e6
mininet_raw["throughput_mbps"] = mininet_raw["throughput_bps"] / 1e6
mininet_raw["memory_percent"] = mininet_raw["memory_after_percent"]

mininet_long = mininet_raw[
    [
        "Nodes",
        "Platform",
        "bandwidth_mbps",
        "throughput_mbps",
        "cpu_percent",
        "memory_percent"
    ]
]


# =========================
# COMBINE RAW LONG DATA
# =========================

combined_raw = pd.concat([seed_long, mininet_long], ignore_index=True)

for col in [
    "bandwidth_mbps",
    "throughput_mbps",
    "cpu_percent",
    "memory_percent"
]:
    combined_raw[col] = pd.to_numeric(combined_raw[col], errors="coerce")

combined_raw = combined_raw.dropna()


# =========================
# STATISTICAL SUMMARY FUNCTION
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

def statistical_summary(metric_col, metric_name):
    seed_vals = combined_raw[
        combined_raw["Platform"] == "SEED IE"
    ][metric_col].dropna()

    mininet_vals = combined_raw[
        combined_raw["Platform"] == "Mininet"
    ][metric_col].dropna()

    u_stat, p_mw = mannwhitneyu(
        mininet_vals,
        seed_vals,
        alternative="two-sided"
    )

    t_stat, p_t = ttest_ind(
        mininet_vals,
        seed_vals,
        equal_var=False
    )

    n1 = len(mininet_vals)
    n2 = len(seed_vals)

    r_rb = 1 - (2 * u_stat) / (n1 * n2)

    return {
        "Metric": metric_name,
        "p (Mann–Whitney)": format_p(p_mw),
        "p (Welch t-test)": format_p(p_t),
        "Effect Size (r_rb)": round(r_rb, 3),
        "Interpretation": interpret_effect(r_rb)
    }


stats_table = pd.DataFrame([
    statistical_summary("bandwidth_mbps", "Bandwidth"),
    statistical_summary("throughput_mbps", "Throughput"),
    statistical_summary("cpu_percent", "CPU Utilisation"),
    statistical_summary("memory_percent", "Memory Utilisation")
])

print("\nSTATISTICAL SUMMARY TABLE")
print(stats_table)

stats_table.to_csv("./docs/tables/statistical_summary_table.csv", index=False)