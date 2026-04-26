import pandas as pd
import numpy as np


mininet_latency =  pd.read_csv('./result/mininet/mininet_raw_latency_time_results.csv')
seed_latency =  pd.read_csv('./result/seed_ie/seed_ie_raw_latency_time_results.csv')

print(mininet_latency.columns)
print(seed_latency.columns)

print(mininet_latency.head())
print(seed_latency.head())

PAIR_COL = "pair"
ITER_COL = "iteration"
LAT_COL = "ping_rtt_ms"

mininet_latency = mininet_latency[[PAIR_COL, ITER_COL, LAT_COL]]
seed_latency = seed_latency[[PAIR_COL, ITER_COL, LAT_COL]]

mininet_latency[LAT_COL] = pd.to_numeric(mininet_latency[LAT_COL], errors="coerce")
seed_latency[LAT_COL] = pd.to_numeric(seed_latency[LAT_COL], errors="coerce")

mininet_latency = mininet_latency.dropna()
seed_latency = seed_latency.dropna()

if seed_latency.duplicated(subset=["pair", "iteration"]).sum() > 0:
    seed_latency = (
        seed_latency
        .groupby(["pair", "iteration"])["ping_rtt_ms"]
        .mean()
        .reset_index()
    )
    
    def create_latency_table(df):
        grouped = df.groupby(PAIR_COL)

        results = []

        for pair, data in grouped:
            lat = data[LAT_COL].values

            results.append({
                "Nodes": pair.replace("_", "-").upper(),
                "Max": np.max(lat),
                "Min": np.min(lat),
                "Avg": np.mean(lat),
                "StdDev": np.std(lat),
                "Median": np.median(lat),
                "Jitter": np.mean(np.abs(lat - np.mean(lat)))
        })

        table = pd.DataFrame(results).round(2)
        return table
    
mininet_table = create_latency_table(mininet_latency)
seed_table = create_latency_table(seed_latency)

HOPS = {
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

mininet_table["Hops"] = mininet_table["Nodes"].map(HOPS)
seed_table["Hops"] = seed_table["Nodes"].map(HOPS)

# reorder columns
cols = ["Nodes", "Hops", "Max", "Min", "Avg", "StdDev", "Median", "Jitter"]

mininet_table = mininet_table[cols]
seed_table = seed_table[cols]

print("\nMininet Latency Table:")
print(mininet_table)

print("\nSEED IE Latency Table:")
print(seed_table)