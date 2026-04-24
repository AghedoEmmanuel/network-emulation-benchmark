#!/usr/bin/env python3

import argparse
import csv
import datetime
import json
import subprocess
import time

DEFAULT_ITERATIONS = 10
IPERF_DURATION = 5
PAUSE_BETWEEN_RUNS = 2.0
OUTPUT_CSV = "seed_ie_throughput_bandwidth_cpu_memory_raw.csv"
OUTPUT_JSON = "seed_ie_throughput_bandwidth_cpu_memory_raw.json"

TEST_PAIRS = [
    {"name": "R1-R2", "key": "r1_r2", "hops": 1, "src_container": "as100r-r1-10.0.12.254", "dst_container": "as100r-r2-10.0.12.253", "dst_ip": "10.0.12.253"},
    {"name": "R1-R3", "key": "r1_r3", "hops": 2, "src_container": "as100r-r1-10.0.12.254", "dst_container": "as100r-r3-10.0.23.253", "dst_ip": "10.0.23.253"},
    {"name": "R3-R2", "key": "r3_r2", "hops": 1, "src_container": "as100r-r3-10.0.23.253", "dst_container": "as100r-r2-10.0.12.253", "dst_ip": "10.0.23.254"},
    {"name": "R3-R6", "key": "r3_r6", "hops": 3, "src_container": "as100r-r3-10.0.23.253", "dst_container": "as100r-r6-10.0.56.253", "dst_ip": "10.0.56.253"},
    {"name": "R1-R6", "key": "r1_r6", "hops": 1, "src_container": "as100r-r1-10.0.12.254", "dst_container": "as100r-r6-10.0.56.253", "dst_ip": "10.0.61.253"},
    {"name": "R2-R5", "key": "r2_r5", "hops": 3, "src_container": "as100r-r2-10.0.12.253", "dst_container": "as100r-r5-10.0.45.253", "dst_ip": "10.0.45.253"},
    {"name": "R4-R5", "key": "r4_r5", "hops": 1, "src_container": "as100r-r4-10.0.34.253", "dst_container": "as100r-r5-10.0.45.253", "dst_ip": "10.0.45.253"},
    {"name": "R4-R6", "key": "r4_r6", "hops": 2, "src_container": "as100r-r4-10.0.34.253", "dst_container": "as100r-r6-10.0.56.253", "dst_ip": "10.0.56.253"},
    {"name": "R6-R1", "key": "r6_r1", "hops": 1, "src_container": "as100r-r6-10.0.56.253", "dst_container": "as100r-r1-10.0.12.254", "dst_ip": "10.0.61.254"},
]


def run_cmd(cmd: str, timeout: int = 90, check: bool = True) -> str:
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=timeout)
    output = (result.stdout or "") + (result.stderr or "")
    if check and result.returncode != 0:
        raise RuntimeError(output.strip() or f"Command failed: {cmd}")
    return output


def docker_exec(container: str, command: str, timeout: int = 90, check: bool = True) -> str:
    safe_command = command.replace('"', '\\"')
    return run_cmd(f'sudo docker exec {container} sh -lc "{safe_command}"', timeout=timeout, check=check)


def get_cpu_snapshot():
    with open("/proc/stat", "r", encoding="utf-8") as f:
        values = list(map(int, f.readline().split()[1:]))
    idle = values[3]
    total = sum(values)
    return idle, total


def get_memory_usage():
    meminfo = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
            key, value = line.split(":")
            meminfo[key] = int(value.strip().split()[0])

    total_kb = meminfo["MemTotal"]
    available_kb = meminfo["MemAvailable"]
    used_kb = total_kb - available_kb

    return round(used_kb / 1024, 6), round((used_kb / total_kb) * 100, 6)


def run_iperf_raw(pair, duration):
    src_container = pair["src_container"]
    dst_container = pair["dst_container"]
    dst_ip = pair["dst_ip"]

    docker_exec(dst_container, "pkill -f iperf3 || true", check=False)
    time.sleep(0.5)
    docker_exec(dst_container, "iperf3 -s -D", check=False)
    time.sleep(1)

    cpu_idle_before, cpu_total_before = get_cpu_snapshot()
    mem_before_mb, mem_before_pct = get_memory_usage()

    started_at = datetime.datetime.now().isoformat()
    start_perf = time.perf_counter()

    error = None
    bandwidth_bps = None
    throughput_bps = None
    success = False

    try:
        output = docker_exec(src_container, f"iperf3 -c {dst_ip} -t {duration} -J", timeout=duration + 30)
        data = json.loads(output)

        bandwidth_bps = data["end"]["sum_sent"]["bits_per_second"]
        throughput_bps = data["end"]["sum_received"]["bits_per_second"]
        success = True

    except Exception as exc:
        error = str(exc)

    elapsed_ms = round((time.perf_counter() - start_perf) * 1000.0, 6)

    cpu_idle_after, cpu_total_after = get_cpu_snapshot()
    mem_after_mb, mem_after_pct = get_memory_usage()

    idle_delta = cpu_idle_after - cpu_idle_before
    total_delta = cpu_total_after - cpu_total_before

    cpu_percent = None
    if total_delta > 0:
        cpu_percent = round(100 * (1 - (idle_delta / total_delta)), 6)

    docker_exec(dst_container, "pkill -f iperf3 || true", check=False)

    return {
        "started_at": started_at,
        "success": success,
        "bandwidth_bps": bandwidth_bps,
        "throughput_bps": throughput_bps,
        "cpu_percent": cpu_percent,
        "memory_before_mb": mem_before_mb,
        "memory_before_percent": mem_before_pct,
        "memory_after_mb": mem_after_mb,
        "memory_after_percent": mem_after_pct,
        "duration_requested_s": duration,
        "elapsed_ms": elapsed_ms,
        "error": error,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--duration", type=int, default=IPERF_DURATION)
    parser.add_argument("--pause", type=float, default=PAUSE_BETWEEN_RUNS)
    parser.add_argument("--csv", default=OUTPUT_CSV)
    parser.add_argument("--json", default=OUTPUT_JSON)
    args = parser.parse_args()

    rows = []

    for iteration in range(1, args.iterations + 1):
        print(f"Iteration {iteration}/{args.iterations}")

        for pair in TEST_PAIRS:
            print(f"  Testing {pair['name']}")

            result = run_iperf_raw(pair, args.duration)

            row = {
                "iteration": iteration,
                "started_at": result["started_at"],
                "pair": pair["name"],
                "pair_key": pair["key"],
                "hops": pair["hops"],
                "src_container": pair["src_container"],
                "dst_container": pair["dst_container"],
                "dst_ip": pair["dst_ip"],
                "success": result["success"],
                "bandwidth_bps": result["bandwidth_bps"],
                "throughput_bps": result["throughput_bps"],
                "cpu_percent": result["cpu_percent"],
                "memory_before_mb": result["memory_before_mb"],
                "memory_before_percent": result["memory_before_percent"],
                "memory_after_mb": result["memory_after_mb"],
                "memory_after_percent": result["memory_after_percent"],
                "duration_requested_s": result["duration_requested_s"],
                "elapsed_ms": result["elapsed_ms"],
                "error": result["error"],
            }

            rows.append(row)

        if iteration < args.iterations and args.pause > 0:
            time.sleep(args.pause)

    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "method": "Raw iperf3 throughput/bandwidth with CPU and memory readings. No descriptive statistics calculated.",
        "iterations_requested": args.iterations,
        "iperf_duration_seconds": args.duration,
        "rows": rows,
    }

    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"CSV saved to {args.csv}")
    print(f"JSON saved to {args.json}")


if __name__ == "__main__":
    main()