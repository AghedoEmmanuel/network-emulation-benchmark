
# benchmark_ospf_complete.py

import subprocess
import time
import csv
import statistics
import json

DEFAULT_ITERATIONS = 1000
CONVERGENCE_ITERATIONS = 30

CSV_RAW = "ospf_raw_iterations.csv"
CSV_SUMMARY = "ospf_summary.csv"
CONV_CSV = "ospf_convergence.csv"
CONV_JSON = "ospf_convergence.json"

TEST_PAIRS = [
    ("R1-R2", 1, "as100r-r1-10.0.12.254", "10.0.12.253"),
    ("R1-R3", 2, "as100r-r1-10.0.12.254", "10.0.23.2"),
]

FAIL_LINK_CMD_DOWN = "ip link set dev net34 down"
FAIL_LINK_CMD_UP = "ip link set dev net34 up"

def run_cmd(cmd):
    return subprocess.check_output(cmd, shell=True).decode()

def docker_exec(container, command):
    return run_cmd(f"docker exec {container} {command}")

def run_ping(container, dst_ip):
    output = docker_exec(container, f"ping -c 10 {dst_ip}")
    return parse_ping_output(output)

def parse_ping_output(output):
    lines = output.split("\n")
    stats_line = [l for l in lines if "min/avg/max" in l]
    if not stats_line:
        return None

    values = stats_line[0].split("=")[1].split("/")
    min_rtt, avg_rtt, max_rtt, stddev = map(float, values)

    samples = []
    for line in lines:
        if "time=" in line:
            samples.append(float(line.split("time=")[1].split()[0]))

    median = statistics.median(samples) if samples else 0
    jitter = statistics.mean([abs(x - avg_rtt) for x in samples]) if samples else 0

    return min_rtt, avg_rtt, max_rtt, stddev, median, jitter

def run_latency_tests():
    raw_rows = []
    summary_rows = []

    for pair_name, hops, container, dst_ip in TEST_PAIRS:
        print(f"Testing {pair_name}")

        latencies = []
        jitters = []

        for i in range(1, DEFAULT_ITERATIONS + 1):
            res = run_ping(container, dst_ip)
            if not res:
                continue

            min_rtt, avg_rtt, max_rtt, stddev, median, jitter = res

            raw_rows.append({
                "iteration": i,
                "pair": pair_name,
                "latency_avg_ms": avg_rtt,
                "latency_min_ms": min_rtt,
                "latency_max_ms": max_rtt,
                "latency_std_ms": stddev,
                "latency_median_ms": median,
                "jitter_ms": jitter
            })

            latencies.append(avg_rtt)
            jitters.append(jitter)

        if not latencies:
            continue

        summary_rows.append({
            "pair": pair_name,
            "hops": hops,
            "avg_latency_ms": statistics.mean(latencies),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "std_latency_ms": statistics.pstdev(latencies),
            "median_latency_ms": statistics.median(latencies),
            "avg_jitter_ms": statistics.mean(jitters)
        })

    with open(CSV_RAW, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=raw_rows[0].keys())
        writer.writeheader()
        writer.writerows(raw_rows)

    with open(CSV_SUMMARY, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

def measure_convergence(container, dst_ip):
    # Bring link down
    docker_exec(container, FAIL_LINK_CMD_DOWN)
    start = time.time()

    while True:
        try:
            docker_exec(container, f"ping -c 1 -W 1 {dst_ip}")
            break
        except:
            pass

    failure_time = (time.time() - start) * 1000  # ms

    # Bring link up
    docker_exec(container, FAIL_LINK_CMD_UP)
    start = time.time()

    while True:
        try:
            docker_exec(container, f"ping -c 1 -W 1 {dst_ip}")
            break
        except:
            pass

    recovery_time = (time.time() - start) * 1000  # ms

    return failure_time, recovery_time

def run_convergence_tests():
    container = TEST_PAIRS[0][2]
    dst_ip = TEST_PAIRS[0][3]

    results = []

    for i in range(CONVERGENCE_ITERATIONS):
        print(f"Convergence iteration {i+1}")
        failure, recovery = measure_convergence(container, dst_ip)

        results.append({
            "iteration": i+1,
            "failure_ms": failure,
            "recovery_ms": recovery
        })

    # Save CSV
    with open(CONV_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    # Save JSON
    with open(CONV_JSON, "w") as f:
        json.dump({
            "summary": {
                "avg_failure_ms": statistics.mean(r["failure_ms"] for r in results),
                "avg_recovery_ms": statistics.mean(r["recovery_ms"] for r in results)
            },
            "raw_results_ms": results
        }, f, indent=2)

if __name__ == "__main__":
    run_latency_tests()
    run_convergence_tests()
