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

seed_summary = (
    seed_long
    .groupby("Nodes")
    .agg(
        Avg_Bandwidth_Mbps=("bandwidth_mbps", "mean"),
        Std_Bandwidth_Mbps=("bandwidth_mbps", "std"),

        Avg_Throughput_Mbps=("throughput_mbps", "mean"),
        Std_Throughput_Mbps=("throughput_mbps", "std"),

        Avg_Retransmits=("retransmits", "mean"),

        Avg_CPU_Percent=("cpu_percent", "mean"),
        Max_CPU_Percent=("cpu_percent", "max"),

        Avg_Memory_Percent=("memory_percent", "mean"),
        Max_Memory_Percent=("memory_percent", "max"),

        Avg_Power_W=("power_w", "mean"),

        # note: this repeats per route because SEED energy is per iteration
        Total_Energy_kWh=("energy_kwh", "sum")
    )
    .reset_index()
    .round(2)
)

print("\nSEED IE Route-Level Summary")
print(seed_summary)


# =========================
# PLATFORM-LEVEL ENERGY SUMMARY
# Better for dissertation energy reporting
# =========================

seed_energy_summary = pd.DataFrame([{
    "Platform": "SEED IE",
    "Avg_CPU_Percent": seed["cpu_total_busy_pct"].mean(),
    "Max_CPU_Percent": seed["cpu_total_busy_pct"].max(),
    "Avg_Memory_Percent": seed["mem_utilisation_pct"].mean(),
    "Max_Memory_Percent": seed["mem_utilisation_pct"].max(),
    "Avg_Power_W": seed["estimated_power_w"].mean(),
    "Total_Energy_kWh": seed["estimated_energy_kwh"].sum()
}]).round(6)

print("\nSEED IE Platform-Level Energy Summary")
print(seed_energy_summary)


# =========================
# OPTIONAL: SAVE TABLES
# =========================

#seed_summary.to_csv("./result/seed_ie/seed_ie_bandwidth_throughput_cpu_memory_route_summary.csv", index=False)
#seed_energy_summary.to_csv("./result/seed_ie/seed_ie_energy_platform_summary.csv", index=False)