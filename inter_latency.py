import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# =========================
# LOAD INTER-EMULATOR LATENCY DATA
# =========================

df = pd.read_csv("./hybrid_system_comparison/hybrid_latency_raw.csv")

print(df.shape)
print(df.columns)
print(df.head())


# =========================
# CLEAN DATA
# =========================

df["rtt_ms"] = pd.to_numeric(df["rtt_ms"], errors="coerce")
df = df.dropna(subset=["rtt_ms"])

df["source_router"] = df["source_router"].astype(str).str.upper()
df["target_name"] = df["target_name"].astype(str).str.upper()

df["Test"] = df["source_router"] + " → " + df["target_name"]


# =========================
# CREATE OUTPUT FOLDERS
# =========================

os.makedirs("./docs/tables", exist_ok=True)
os.makedirs("./docs/figures", exist_ok=True)


# =========================
# INTER-EMULATOR LATENCY TABLE
# =========================

inter_emulator_latency_table = (
    df
    .groupby("Test")
    .agg(
        Samples=("rtt_ms", "count"),
        Min_ms=("rtt_ms", "min"),
        Max_ms=("rtt_ms", "max"),
        Mean_ms=("rtt_ms", "mean"),
        Median_ms=("rtt_ms", "median"),
        Std_Dev_ms=("rtt_ms", "std")
    )
    .reset_index()
    .round(3)
)

print("\nINTER-EMULATOR LATENCY SUMMARY")
print(inter_emulator_latency_table)

inter_emulator_latency_table.to_csv(
    "./docs/tables/inter_emulator_latency_summary.csv",
    index=False
)


# =========================
# OVERALL SUMMARY TABLE
# =========================

overall_inter_emulator_summary = pd.DataFrame([{
    "Test": "Mininet ↔ SEED IE",
    "Samples": len(df),
    "Min (ms)": df["rtt_ms"].min(),
    "Max (ms)": df["rtt_ms"].max(),
    "Mean (ms)": df["rtt_ms"].mean(),
    "Median (ms)": df["rtt_ms"].median(),
    "Std Dev (ms)": df["rtt_ms"].std()
}]).round(3)

print("\nOVERALL INTER-EMULATOR LATENCY SUMMARY")
print(overall_inter_emulator_summary)

overall_inter_emulator_summary.to_csv(
    "./docs/tables/overall_inter_emulator_latency_summary.csv",
    index=False
)


# =========================
# BAR CHART: MEAN LATENCY BY TEST
# =========================

plot_data = inter_emulator_latency_table.sort_values(
    by="Mean_ms",
    ascending=False
)

plt.figure(figsize=(12, 6))
plt.bar(plot_data["Test"], plot_data["Mean_ms"])

plt.xlabel("Inter-Emulator Test Path")
plt.ylabel("Mean RTT Latency (ms)")
plt.title("Inter-Emulator Latency Test: Mininet to SEED IE")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()

plt.savefig(
    "./docs/figures/inter_emulator_latency_bar_chart.png",
    dpi=300
)

plt.show()