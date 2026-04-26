#!/usr/bin/env python3
"""
final_comparison_script.py

Final comparison script for dissertation benchmarking.

Purpose:
- Compare Mininet FRR OSPF results against SEED IE BIRD/OSPF results.
- Produce Lewis-style latency tables:
  Nodes | Hops | Max | Min | Avg | StdDev | Median | Jitter
- Produce throughput/bandwidth/resource summaries.
- Produce convergence summaries.
- Produce statistical comparison tables using Mann-Whitney U and Welch's t-test.
- Save all outputs as CSV files.

Expected input files
--------------------
Mininet:
  ./result/mininet/mininet_raw_latency_time_results.csv
  ./result/mininet/mininet_throughput_bandwidth_cpu_memory_raw.csv
  ./result/mininet/mininet_convergence_time_results.csv

SEED IE:
  ./result/seed_ie/seed_ie_raw_latency_time_results.csv
  ./result/seed_ie/seed_ie_throughput_bandwidth_cpu_memory_raw.csv
  ./result/seed_ie/seed_ie_convergence_time_results.csv

Output folder:
  ./result/final_comparison/

Notes:
- This script assumes both emulators use the same pair naming style:
  R1-R2, R1-R3, R3-R2, R3-R6, R1-R6, R2-R5, R4-R5, R4-R6, R6-R1
- Jitter is calculated as mean absolute deviation from mean RTT, matching the Lewis-style table.
- Welch's t-test and Mann-Whitney U test are used where scipy is available.
"""

import os
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scipy.stats import mannwhitneyu, ttest_ind
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False
    warnings.warn("scipy is not installed. Statistical test columns will be filled with NaN.")


# ============================================================
# PATHS
# ============================================================

MININET_LATENCY = "./result/mininet/mininet_raw_latency_time_results.csv"
SEED_LATENCY = "./result/seed_ie/seed_ie_raw_latency_time_results.csv"

MININET_TBCM = "./result/mininet/mininet_throughput_bandwidth_cpu_memory_raw.csv"
SEED_TBCM = "./result/seed_ie/seed_ie_throughput_bandwidth_cpu_memory_raw.csv"

MININET_CONV = "./result/mininet/mininet_convergence_time_results.csv"
SEED_CONV = "./result/seed_ie/seed_ie_convergence_time_results.csv"

OUTPUT_DIR = Path("./result/final_comparison")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# ROUTE / HOP CONFIGURATION
# ============================================================

PAIR_ORDER = [
    "R1-R2",
    "R1-R3",
    "R3-R2",
    "R3-R6",
    "R1-R6",
    "R2-R5",
    "R4-R5",
    "R4-R6",
    "R6-R1",
]

HOPS = {
    "R1-R2": 1,
    "R1-R3": 2,
    "R3-R2": 1,
    "R3-R6": 3,
    "R1-R6": 1,
    "R2-R5": 3,
    "R4-R5": 1,
    "R4-R6": 2,
    "R6-R1": 1,
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalise_pair_name(value):
    """
    Converts pair labels into a common format such as R1-R2.
    Handles inputs such as:
    - R1-R2
    - r1_r2
    - r1-r2
    """
    if pd.isna(value):
        return np.nan

    text = str(value).strip().upper()
    text = text.replace("_", "-")
    text = text.replace(" ", "")

    return text


def safe_read_csv(path, required=True):
    """
    Read a CSV file and return a dataframe.
    """
    if not os.path.exists(path):
        msg = f"Missing file: {path}"
        if required:
            raise FileNotFoundError(msg)
        print(f"Warning: {msg}")
        return pd.DataFrame()

    df = pd.read_csv(path)
    print(f"Loaded {path}: {df.shape}")
    return df


def numeric(series):
    return pd.to_numeric(series, errors="coerce")


def mean_abs_deviation(values):
    """
    Lewis-style jitter calculation:
    mean absolute deviation from the average RTT.
    """
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]

    if len(values) == 0:
        return np.nan

    avg = np.mean(values)
    return np.mean(np.abs(values - avg))


def describe_values(values):
    """
    Returns descriptive statistics for a numeric array.
    """
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]

    if len(values) == 0:
        return {
            "Count": 0,
            "Max": np.nan,
            "Min": np.nan,
            "Avg": np.nan,
            "StdDev": np.nan,
            "Median": np.nan,
            "Jitter": np.nan,
        }

    return {
        "Count": len(values),
        "Max": np.max(values),
        "Min": np.min(values),
        "Avg": np.mean(values),
        "StdDev": np.std(values, ddof=0),
        "Median": np.median(values),
        "Jitter": mean_abs_deviation(values),
    }


def statistical_tests(x, y):
    """
    Runs Mann-Whitney U and Welch's t-test between two numeric arrays.
    """
    x = pd.to_numeric(pd.Series(x), errors="coerce").dropna().values
    y = pd.to_numeric(pd.Series(y), errors="coerce").dropna().values

    if len(x) < 2 or len(y) < 2 or not SCIPY_AVAILABLE:
        return {
            "Mann_Whitney_U_p": np.nan,
            "Welch_t_p": np.nan,
            "Rank_Biserial_r": np.nan,
        }

    try:
        mw = mannwhitneyu(x, y, alternative="two-sided")
        mw_p = mw.pvalue

        # Rank-biserial effect size.
        # r_rb = 1 - (2U)/(n1*n2)
        # Direction depends on the ordering of x and y.
        n1, n2 = len(x), len(y)
        u = mw.statistic
        r_rb = 1 - (2 * u) / (n1 * n2)

    except Exception:
        mw_p = np.nan
        r_rb = np.nan

    try:
        wt = ttest_ind(x, y, equal_var=False, nan_policy="omit")
        wt_p = wt.pvalue
    except Exception:
        wt_p = np.nan

    return {
        "Mann_Whitney_U_p": mw_p,
        "Welch_t_p": wt_p,
        "Rank_Biserial_r": r_rb,
    }


def format_p_value(p):
    if pd.isna(p):
        return np.nan
    if p < 0.0001:
        return "<0.0001"
    return round(float(p), 6)


def save_csv(df, filename):
    path = OUTPUT_DIR / filename
    df.to_csv(path, index=False)
    print(f"Saved: {path}")
    return path


# ============================================================
# LATENCY AND JITTER ANALYSIS
# ============================================================

def load_latency_data(path, platform):
    df = safe_read_csv(path)

    required_cols = ["pair", "ping_rtt_ms"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"{platform} latency file is missing columns: {missing}")

    df = df.copy()
    df["Platform"] = platform
    df["Nodes"] = df["pair"].apply(normalise_pair_name)
    df["Hops"] = df["Nodes"].map(HOPS)
    df["ping_rtt_ms"] = numeric(df["ping_rtt_ms"])

    if "success" in df.columns:
        df["success_clean"] = df["success"].astype(str).str.lower().str.strip()
        df = df[df["success_clean"].isin(["true", "1", "yes"])].copy()

    df = df.dropna(subset=["Nodes", "ping_rtt_ms"])
    df = df[df["Nodes"].isin(PAIR_ORDER)].copy()

    return df


def create_latency_table(df, platform):
    rows = []

    for pair in PAIR_ORDER:
        values = df.loc[df["Nodes"] == pair, "ping_rtt_ms"].values
        stats = describe_values(values)

        rows.append({
            "Platform": platform,
            "Nodes": pair,
            "Hops": HOPS.get(pair),
            "Max": stats["Max"],
            "Min": stats["Min"],
            "Avg": stats["Avg"],
            "StdDev": stats["StdDev"],
            "Median": stats["Median"],
            "Jitter": stats["Jitter"],
            "Count": stats["Count"],
        })

    return pd.DataFrame(rows)


def analyse_latency():
    mininet = load_latency_data(MININET_LATENCY, "Mininet")
    seed = load_latency_data(SEED_LATENCY, "SEED IE")

    mininet_table = create_latency_table(mininet, "Mininet")
    seed_table = create_latency_table(seed, "SEED IE")

    combined_table = pd.concat([mininet_table, seed_table], ignore_index=True)

    # Direct comparison per route.
    comparison_rows = []
    for pair in PAIR_ORDER:
        m_vals = mininet.loc[mininet["Nodes"] == pair, "ping_rtt_ms"]
        s_vals = seed.loc[seed["Nodes"] == pair, "ping_rtt_ms"]

        m_avg = m_vals.mean()
        s_avg = s_vals.mean()

        tests = statistical_tests(m_vals, s_vals)

        comparison_rows.append({
            "Metric": "Latency",
            "Nodes": pair,
            "Hops": HOPS.get(pair),
            "Mininet_Avg_ms": m_avg,
            "SEED_IE_Avg_ms": s_avg,
            "Difference_ms_Mininet_minus_SEED": m_avg - s_avg,
            "Percent_Difference_vs_Mininet": ((m_avg - s_avg) / m_avg * 100) if m_avg else np.nan,
            "Better_Platform": "SEED IE" if s_avg < m_avg else "Mininet",
            "Mann_Whitney_U_p": tests["Mann_Whitney_U_p"],
            "Welch_t_p": tests["Welch_t_p"],
            "Rank_Biserial_r": tests["Rank_Biserial_r"],
        })

    comparison = pd.DataFrame(comparison_rows)

    # Round for dissertation readability.
    combined_table_rounded = combined_table.round(6)
    comparison_rounded = comparison.copy()
    comparison_rounded["Mann_Whitney_U_p"] = comparison_rounded["Mann_Whitney_U_p"].apply(format_p_value)
    comparison_rounded["Welch_t_p"] = comparison_rounded["Welch_t_p"].apply(format_p_value)
    comparison_rounded = comparison_rounded.round(6)

    save_csv(mininet_table.round(6), "mininet_latency_lewis_style_table.csv")
    save_csv(seed_table.round(6), "seed_ie_latency_lewis_style_table.csv")
    save_csv(combined_table_rounded, "combined_latency_lewis_style_table.csv")
    save_csv(comparison_rounded, "latency_statistical_comparison.csv")

    return mininet, seed, combined_table, comparison


# ============================================================
# THROUGHPUT, BANDWIDTH, CPU, MEMORY AND ENERGY
# ============================================================

def load_tbcm_mininet(path):
    df = safe_read_csv(path)
    df = df.copy()

    if "success" in df.columns:
        df["success_clean"] = df["success"].astype(str).str.lower().str.strip()
        df = df[df["success_clean"].isin(["true", "1", "yes"])].copy()

    df["Platform"] = "Mininet"
    df["Nodes"] = df["pair"].apply(normalise_pair_name)

    numeric_cols = [
        "bandwidth_bps",
        "throughput_bps",
        "cpu_percent",
        "memory_before_percent",
        "memory_after_percent",
        "memory_before_mb",
        "memory_after_mb",
        "elapsed_ms",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = numeric(df[col])

    df["bandwidth_mbps"] = df["bandwidth_bps"] / 1e6
    df["throughput_mbps"] = df["throughput_bps"] / 1e6

    # Use memory after the run as the utilisation value.
    df["memory_percent"] = df.get("memory_after_percent", np.nan)
    df["memory_used_mb"] = df.get("memory_after_mb", np.nan)

    # Mininet energy estimate using same simple CPU-based model.
    # Adjust if your dissertation uses different idle/max values.
    IDLE_POWER_W = 50.0
    MAX_POWER_W = 150.0

    df["estimated_power_w"] = IDLE_POWER_W + (df["cpu_percent"] / 100.0) * (MAX_POWER_W - IDLE_POWER_W)
    df["time_hours"] = df["elapsed_ms"] / (1000.0 * 3600.0)
    df["estimated_energy_kwh"] = (df["estimated_power_w"] * df["time_hours"]) / 1000.0

    return df


def load_tbcm_seed(path):
    df = safe_read_csv(path)
    df = df.copy()

    if "success" in df.columns:
        df["success_clean"] = df["success"].astype(str).str.lower().str.strip()
        df = df[df["success_clean"].isin(["true", "1", "yes"])].copy()

    df["Platform"] = "SEED IE"
    df["Nodes"] = df["pair"].apply(normalise_pair_name)

    numeric_cols = [
        "bandwidth_bps",
        "throughput_bps",
        "cpu_percent",
        "memory_before_percent",
        "memory_after_percent",
        "memory_before_mb",
        "memory_after_mb",
        "elapsed_ms",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = numeric(df[col])

    df["bandwidth_mbps"] = df["bandwidth_bps"] / 1e6
    df["throughput_mbps"] = df["throughput_bps"] / 1e6
    df["memory_percent"] = df.get("memory_after_percent", np.nan)
    df["memory_used_mb"] = df.get("memory_after_mb", np.nan)

    # SEED raw TBCM script does not always include energy.
    # Estimate it using a conservative Docker-side model if not present.
    IDLE_POWER_W = 20.0
    MAX_POWER_W = 60.0

    df["estimated_power_w"] = IDLE_POWER_W + (df["cpu_percent"] / 100.0) * (MAX_POWER_W - IDLE_POWER_W)
    df["time_hours"] = df["elapsed_ms"] / (1000.0 * 3600.0)
    df["estimated_energy_kwh"] = (df["estimated_power_w"] * df["time_hours"]) / 1000.0

    return df


def create_tbcm_summary(df):
    grouped = (
        df.groupby(["Platform", "Nodes"], dropna=False)
        .agg(
            Hops=("Nodes", lambda x: HOPS.get(x.iloc[0], np.nan)),
            Avg_Bandwidth_Mbps=("bandwidth_mbps", "mean"),
            Std_Bandwidth_Mbps=("bandwidth_mbps", "std"),
            Avg_Throughput_Mbps=("throughput_mbps", "mean"),
            Std_Throughput_Mbps=("throughput_mbps", "std"),
            Avg_CPU_Percent=("cpu_percent", "mean"),
            Max_CPU_Percent=("cpu_percent", "max"),
            Avg_Memory_Percent=("memory_percent", "mean"),
            Max_Memory_Percent=("memory_percent", "max"),
            Avg_Memory_MB=("memory_used_mb", "mean"),
            Max_Memory_MB=("memory_used_mb", "max"),
            Avg_Power_W=("estimated_power_w", "mean"),
            Total_Energy_kWh=("estimated_energy_kwh", "sum"),
            Count=("Nodes", "count"),
        )
        .reset_index()
    )

    grouped["Nodes"] = pd.Categorical(grouped["Nodes"], categories=PAIR_ORDER, ordered=True)
    grouped = grouped.sort_values(["Platform", "Nodes"]).reset_index(drop=True)

    return grouped


def compare_metric_by_pair(mininet, seed, metric_col, metric_name, higher_is_better):
    rows = []

    for pair in PAIR_ORDER:
        m_vals = mininet.loc[mininet["Nodes"] == pair, metric_col]
        s_vals = seed.loc[seed["Nodes"] == pair, metric_col]

        m_avg = m_vals.mean()
        s_avg = s_vals.mean()

        if higher_is_better:
            better = "SEED IE" if s_avg > m_avg else "Mininet"
            percent_change = ((s_avg - m_avg) / m_avg * 100) if m_avg else np.nan
        else:
            better = "SEED IE" if s_avg < m_avg else "Mininet"
            percent_change = ((m_avg - s_avg) / m_avg * 100) if m_avg else np.nan

        tests = statistical_tests(m_vals, s_vals)

        rows.append({
            "Metric": metric_name,
            "Nodes": pair,
            "Hops": HOPS.get(pair),
            "Mininet_Avg": m_avg,
            "SEED_IE_Avg": s_avg,
            "Difference_SEED_minus_Mininet": s_avg - m_avg,
            "Percent_Change_vs_Mininet": percent_change,
            "Better_Platform": better,
            "Mann_Whitney_U_p": tests["Mann_Whitney_U_p"],
            "Welch_t_p": tests["Welch_t_p"],
            "Rank_Biserial_r": tests["Rank_Biserial_r"],
        })

    return pd.DataFrame(rows)


def analyse_tbcm():
    mininet = load_tbcm_mininet(MININET_TBCM)
    seed = load_tbcm_seed(SEED_TBCM)

    combined = pd.concat([mininet, seed], ignore_index=True)
    summary = create_tbcm_summary(combined)

    comparisons = []
    comparisons.append(compare_metric_by_pair(mininet, seed, "bandwidth_mbps", "Bandwidth Mbps", higher_is_better=True))
    comparisons.append(compare_metric_by_pair(mininet, seed, "throughput_mbps", "Throughput Mbps", higher_is_better=True))
    comparisons.append(compare_metric_by_pair(mininet, seed, "cpu_percent", "CPU Utilisation %", higher_is_better=False))
    comparisons.append(compare_metric_by_pair(mininet, seed, "memory_percent", "Memory Utilisation %", higher_is_better=False))
    comparisons.append(compare_metric_by_pair(mininet, seed, "estimated_power_w", "Estimated Power W", higher_is_better=False))
    comparison = pd.concat(comparisons, ignore_index=True)

    comparison_out = comparison.copy()
    comparison_out["Mann_Whitney_U_p"] = comparison_out["Mann_Whitney_U_p"].apply(format_p_value)
    comparison_out["Welch_t_p"] = comparison_out["Welch_t_p"].apply(format_p_value)
    comparison_out = comparison_out.round(6)

    save_csv(summary.round(6), "throughput_bandwidth_cpu_memory_energy_summary.csv")
    save_csv(comparison_out, "throughput_bandwidth_cpu_memory_energy_statistical_comparison.csv")

    return mininet, seed, summary, comparison


# ============================================================
# CONVERGENCE ANALYSIS
# ============================================================

def load_convergence(path, platform):
    df = safe_read_csv(path)
    df = df.copy()
    df["Platform"] = platform

    for col in ["failure_ms", "recovery_ms"]:
        if col not in df.columns:
            raise ValueError(f"{platform} convergence file is missing column: {col}")
        df[col] = numeric(df[col])

    df = df.dropna(subset=["failure_ms", "recovery_ms"], how="all")
    return df


def analyse_convergence():
    mininet = load_convergence(MININET_CONV, "Mininet")
    seed = load_convergence(SEED_CONV, "SEED IE")

    combined = pd.concat([mininet, seed], ignore_index=True)

    summary = (
        combined.groupby("Platform")
        .agg(
            Failure_Count=("failure_ms", "count"),
            Failure_Mean_ms=("failure_ms", "mean"),
            Failure_Median_ms=("failure_ms", "median"),
            Failure_Min_ms=("failure_ms", "min"),
            Failure_Max_ms=("failure_ms", "max"),
            Failure_StdDev_ms=("failure_ms", "std"),
            Recovery_Count=("recovery_ms", "count"),
            Recovery_Mean_ms=("recovery_ms", "mean"),
            Recovery_Median_ms=("recovery_ms", "median"),
            Recovery_Min_ms=("recovery_ms", "min"),
            Recovery_Max_ms=("recovery_ms", "max"),
            Recovery_StdDev_ms=("recovery_ms", "std"),
        )
        .reset_index()
    )

    comparison_rows = []
    for metric_col, label in [("failure_ms", "Failure Convergence"), ("recovery_ms", "Recovery Convergence")]:
        m_vals = mininet[metric_col]
        s_vals = seed[metric_col]
        tests = statistical_tests(m_vals, s_vals)

        m_avg = m_vals.mean()
        s_avg = s_vals.mean()

        comparison_rows.append({
            "Metric": label,
            "Mininet_Avg_ms": m_avg,
            "SEED_IE_Avg_ms": s_avg,
            "Difference_ms_SEED_minus_Mininet": s_avg - m_avg,
            "Percent_Reduction_vs_Mininet": ((m_avg - s_avg) / m_avg * 100) if m_avg else np.nan,
            "Better_Platform": "SEED IE" if s_avg < m_avg else "Mininet",
            "Mann_Whitney_U_p": tests["Mann_Whitney_U_p"],
            "Welch_t_p": tests["Welch_t_p"],
            "Rank_Biserial_r": tests["Rank_Biserial_r"],
        })

    comparison = pd.DataFrame(comparison_rows)
    comparison["Mann_Whitney_U_p"] = comparison["Mann_Whitney_U_p"].apply(format_p_value)
    comparison["Welch_t_p"] = comparison["Welch_t_p"].apply(format_p_value)

    save_csv(summary.round(6), "convergence_summary.csv")
    save_csv(comparison.round(6), "convergence_statistical_comparison.csv")

    return mininet, seed, summary, comparison


# ============================================================
# CONSOLIDATED SUMMARY
# ============================================================

def build_consolidated_summary(latency_comp, tbcm_comp, conv_comp):
    rows = []

    # Overall averages from comparison tables.
    def avg_for_metric(df, metric_name, mininet_col="Mininet_Avg", seed_col="SEED_IE_Avg"):
        sub = df[df["Metric"] == metric_name]
        return sub[mininet_col].mean(), sub[seed_col].mean()

    lat_m = latency_comp["Mininet_Avg_ms"].mean()
    lat_s = latency_comp["SEED_IE_Avg_ms"].mean()

    rows.append({
        "Metric": "Latency (ms)",
        "Mininet_Mean": lat_m,
        "SEED_IE_Mean": lat_s,
        "Preferred_Direction": "Lower is better",
        "Better_Platform": "SEED IE" if lat_s < lat_m else "Mininet",
    })

    for metric_name, direction, higher_is_better in [
        ("Bandwidth Mbps", "Higher is better", True),
        ("Throughput Mbps", "Higher is better", True),
        ("CPU Utilisation %", "Lower is better", False),
        ("Memory Utilisation %", "Lower is better", False),
        ("Estimated Power W", "Lower is better", False),
    ]:
        m, s = avg_for_metric(tbcm_comp, metric_name)

        if higher_is_better:
            better = "SEED IE" if s > m else "Mininet"
        else:
            better = "SEED IE" if s < m else "Mininet"

        rows.append({
            "Metric": metric_name,
            "Mininet_Mean": m,
            "SEED_IE_Mean": s,
            "Preferred_Direction": direction,
            "Better_Platform": better,
        })

    for _, row in conv_comp.iterrows():
        m = row["Mininet_Avg_ms"]
        s = row["SEED_IE_Avg_ms"]
        rows.append({
            "Metric": row["Metric"] + " (ms)",
            "Mininet_Mean": m,
            "SEED_IE_Mean": s,
            "Preferred_Direction": "Lower is better",
            "Better_Platform": "SEED IE" if s < m else "Mininet",
        })

    consolidated = pd.DataFrame(rows).round(6)
    save_csv(consolidated, "consolidated_performance_summary.csv")
    return consolidated


# ============================================================
# MAIN
# ============================================================

def main():
    print("\n=== FINAL DISSERTATION COMPARISON SCRIPT ===\n")

    print("\n--- Analysing latency and jitter ---")
    mininet_latency, seed_latency, latency_table, latency_comp = analyse_latency()

    print("\n--- Analysing throughput, bandwidth, CPU, memory and energy ---")
    mininet_tbcm, seed_tbcm, tbcm_summary, tbcm_comp = analyse_tbcm()

    print("\n--- Analysing convergence ---")
    mininet_conv, seed_conv, conv_summary, conv_comp = analyse_convergence()

    print("\n--- Building consolidated summary ---")
    consolidated = build_consolidated_summary(latency_comp, tbcm_comp, conv_comp)

    print("\nDone. All outputs saved in:")
    print(f"  {OUTPUT_DIR.resolve()}")

    print("\nMain files to use in your dissertation:")
    print("  1. combined_latency_lewis_style_table.csv")
    print("  2. latency_statistical_comparison.csv")
    print("  3. throughput_bandwidth_cpu_memory_energy_summary.csv")
    print("  4. throughput_bandwidth_cpu_memory_energy_statistical_comparison.csv")
    print("  5. convergence_summary.csv")
    print("  6. convergence_statistical_comparison.csv")
    print("  7. consolidated_performance_summary.csv")


if __name__ == "__main__":
    main()
