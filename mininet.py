import pandas as pd
import numpy as np

df = pd.read_csv("./result/mininet/mininet_throughput_bandwidth_cpu_memory_raw.csv")

print(df.shape)
print(df["success"].value_counts(dropna=False))

# safer success filter
df["success_clean"] = df["success"].astype(str).str.lower().str.strip()
df = df[df["success_clean"].isin(["true", "1", "yes"])].copy()

print("After success filter:", df.shape)

df["pair"] = df["pair"].astype(str).str.strip()

numeric_cols = [
    "bandwidth_bps",
    "throughput_bps",
    "cpu_percent",
    "memory_before_percent",
    "memory_after_percent",
    "elapsed_ms"
]

for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

print("Missing values after numeric conversion:")
print(df[numeric_cols].isna().sum())

df = df.dropna(subset=numeric_cols)

df["bandwidth_mbps"] = df["bandwidth_bps"] / 1e6
df["throughput_mbps"] = df["throughput_bps"] / 1e6
df["memory_utilisation"] = df["memory_after_percent"]

IDLE_POWER = 50
MAX_POWER = 150

df["power_w"] = IDLE_POWER + (df["cpu_percent"] / 100) * (MAX_POWER - IDLE_POWER)
df["time_hours"] = df["elapsed_ms"] / (1000 * 3600)
df["energy_kwh"] = (df["power_w"] * df["time_hours"]) / 1000

table = (
    df.groupby("pair")
    .agg(
        Avg_Bandwidth_Mbps=("bandwidth_mbps", "mean"),
        Std_Bandwidth_Mbps=("bandwidth_mbps", "std"),
        Avg_Throughput_Mbps=("throughput_mbps", "mean"),
        Std_Throughput_Mbps=("throughput_mbps", "std"),
        Avg_CPU_Percent=("cpu_percent", "mean"),
        Max_CPU_Percent=("cpu_percent", "max"),
        Avg_Memory_Percent=("memory_utilisation", "mean"),
        Max_Memory_Percent=("memory_utilisation", "max"),
        Avg_Power_W=("power_w", "mean"),
        Total_Energy_kWh=("energy_kwh", "sum")
    )
    .reset_index()
)

table["Nodes"] = table["pair"].str.replace("_", "-", regex=False).str.upper()
table = table.drop(columns=["pair"])

table = table[
    [
        "Nodes",
        "Avg_Bandwidth_Mbps",
        "Std_Bandwidth_Mbps",
        "Avg_Throughput_Mbps",
        "Std_Throughput_Mbps",
        "Avg_CPU_Percent",
        "Max_CPU_Percent",
        "Avg_Memory_Percent",
        "Max_Memory_Percent",
        "Avg_Power_W",
        "Total_Energy_kWh"
    ]
].round(2)

print(table)