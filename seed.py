import pandas as pd
import numpy as np

# =========================
# LOAD SEED IE DATA
# =========================

seed = pd.read_csv("./result/seed_ie/ospf_benchmark_results_iterative_ms.csv")

print(seed.shape)
print(seed.columns)
print(seed.head())


# =========================
# NODE PAIRS TESTED
# =========================

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


# =========================
# CONVERT WIDE SEED IE DATA TO LONG FORMAT
# =========================

rows = []

for _, row in seed.iterrows():
    for pair in pairs:
        rows.append({
            "iteration": row["iteration"],
            "pair": pair,
            "Nodes": pair.replace("_", "-").upper(),

            # already in Mbps in SEED IE file
            "bandwidth_mbps": row[f"bandwidth_{pair}_mbps"],
            "throughput_mbps": row[f"throughput_{pair}_mbps"],

            # optional but useful
            "retransmits": row[f"retransmits_{pair}"],

            # resource usage
            "cpu_percent": row["cpu_total_busy_pct"],
            "memory_percent": row["mem_utilisation_pct"],

            # SEED IE already has estimated power and energy
            "power_w": row["estimated_power_w"],
            "energy_kwh": row["estimated_energy_kwh"]
        })

seed_long = pd.DataFrame(rows)

print(seed_long.head())


# =========================
# CLEAN NUMERIC COLUMNS
# =========================

numeric_cols = [
    "bandwidth_mbps",
    "throughput_mbps",
    "retransmits",
    "cpu_percent",
    "memory_percent",
    "power_w",
    "energy_kwh"
]

for col in numeric_cols:
    seed_long[col] = pd.to_numeric(seed_long[col], errors="coerce")

seed_long = seed_long.dropna(subset=numeric_cols)


# =========================
# ROUTE-LEVEL SUMMARY TABLE
# =========================

# =========================
# RO
# =========================

# =========================
# TABLE 1: BANDWIDTH SUMMARY
# =========================

seed_bandwidth_table = (
    seed_long
    .groupby("Nodes")
    .agg(
        Mean_Bandwidth_Mbps=("bandwidth_mbps", "mean"),
        Median_Bandwidth_Mbps=("bandwidth_mbps", "median"),
        Min_Bandwidth_Mbps=("bandwidth_mbps", "min"),
        Max_Bandwidth_Mbps=("bandwidth_mbps", "max"),
        Std_Bandwidth_Mbps=("bandwidth_mbps", "std")
    )
    .reset_index()
    .round(3)
)

print("\nSEED IE Bandwidth Summary")
print(seed_bandwidth_table)


# =========================
# TABLE 2: THROUGHPUT SUMMARY
# =========================
seed_throughput_table = (
    seed_long
    .groupby("Nodes")
    .agg(
        Mean_Throughput_Mbps=("throughput_mbps", "mean"),
        Median_Throughput_Mbps=("throughput_mbps", "median"),
        Min_Throughput_Mbps=("throughput_mbps", "min"),
        Max_Throughput_Mbps=("throughput_mbps", "max"),
        Std_Throughput_Mbps=("throughput_mbps", "std")
    )
    .reset_index()
    .round(3)
)

print("\nSEED IE Throughput Summary")
print(seed_throughput_table)


# =========================
# TABLE 3: RESOURCE OVERHEAD SUMMARY
# =========================

seed_resource_table = (
    seed_long
    .groupby("Nodes")
    .agg(
        Mean_CPU_Percent=("cpu_percent", "mean"),
        Median_CPU_Percent=("cpu_percent", "median"),
        Min_CPU_Percent=("cpu_percent", "min"),
        Max_CPU_Percent=("cpu_percent", "max"),
        Std_CPU_Percent=("cpu_percent", "std"),
         Mean_Memory_Percent=("memory_percent", "mean"),
        Median_Memory_Percent=("memory_percent", "median"),
        Min_Memory_Percent=("memory_percent", "min"),
        Max_Memory_Percent=("memory_percent", "max"),
        Std_Memory_Percent=("memory_percent", "std")
    )
    .reset_index()
    .round(3)
)

print("\nSEED IE Resource Overhead Summary")
print(seed_resource_table)


# =========================
# OPTIONAL: SAVE ONLY THESE THREE TABLES
# =========================

seed_bandwidth_table.to_csv("./docs/tables/seed_ie_bandwidth_route_summary.csv", index=False)
seed_throughput_table.to_csv("./docs/tables/seed_ie_throughput_route_summary.csv", index=False)
seed_resource_table.to_csv("./docs/tables/seed_ie_resource_overhead_route_summary.csv", index=False)


# =========================
# PLATFORM-LEVEL ENERGY SUMMARY
# Better for dissertation energy reporting
# =========================

# seed_energy_summary = pd.DataFrame([{
#     "Platform": "SEED IE",
#     "Avg_CPU_Percent": seed["cpu_total_busy_pct"].mean(),
#     "Max_CPU_Percent": seed["cpu_total_busy_pct"].max(),
#     "Avg_Memory_Percent": seed["mem_utilisation_pct"].mean(),
#     "Max_Memory_Percent": seed["mem_utilisation_pct"].max(),
#     "Avg_Power_W": seed["estimated_power_w"].mean(),
#     "Total_Energy_kWh": seed["estimated_energy_kwh"].sum()
# }]).round(6)

# print("\nSEED IE Platform-Level Energy Summary")
# print(seed_energy_summary)
