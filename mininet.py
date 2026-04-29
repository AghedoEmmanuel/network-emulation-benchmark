import pandas as pd
import numpy as np

# =========================
# LOAD MININET DATA
# =========================

df = pd.read_csv("./result/mininet/mininet_throughput_bandwidth_cpu_memory_raw.csv")

print(df.shape)
print(df["success"].value_counts(dropna=False))


# =========================
# FILTER SUCCESSFUL RUNS
# =========================

df["success_clean"] = df["success"].astype(str).str.lower().str.strip()
df = df[df["success_clean"].isin(["true", "1", "yes"])].copy()

print("After success filter:", df.shape)


# =========================
# CLEAN PAIR NAMES
# =========================

df["pair"] = df["pair"].astype(str).str.strip()
df["Nodes"] = df["pair"].str.replace("_", "-", regex=False).str.upper()


# =========================
# CLEAN NUMERIC COLUMNS
# =========================

numeric_cols = [
    "bandwidth_bps",
    "throughput_bps",
    "cpu_percent",
    "memory_after_percent"
]

for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

print("Missing values after numeric conversion:")
print(df[numeric_cols].isna().sum())

df = df.dropna(subset=numeric_cols)


# =========================
# UNIT CONVERSION
# =========================

df["bandwidth_mbps"] = df["bandwidth_bps"] / 1e6
df["throughput_mbps"] = df["throughput_bps"] / 1e6
df["memory_percent"] = df["memory_after_percent"]


# =========================
# TABLE 1: BANDWIDTH SUMMARY
# =========================

mininet_bandwidth_table = (
    df
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

print("\nMININET Bandwidth Summary")
print(mininet_bandwidth_table)


# =========================
# TABLE 2: THROUGHPUT SUMMARY
# =========================

mininet_throughput_table = (
    df
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

print("\nMININET Throughput Summary")
print(mininet_throughput_table)


# =========================
# TABLE 3: RESOURCE OVERHEAD SUMMARY
# =========================

mininet_resource_table = (
    df
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

print("\nMININET Resource Overhead Summary")
print(mininet_resource_table)


# =========================
# OPTIONAL: SAVE ONLY THESE THREE TABLES
# =========================

mininet_bandwidth_table.to_csv("./docs/tables/mininet_bandwidth_route_summary.csv", index=False)
mininet_throughput_table.to_csv("./docs/tables/mininet_throughput_route_summary.csv", index=False)
mininet_resource_table.to_csv("./docs/tables/mininet_resource_overhead_route_summary.csv", index=False)