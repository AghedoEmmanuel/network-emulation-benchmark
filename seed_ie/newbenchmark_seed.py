#!/usr/bin/env python3
"""
Focused raw latency + convergence benchmark for SEED IE.

This version saves every raw latency sample. It does not calculate mean, min, max,
median, stdev or jitter inside the benchmark. You can do those later in Excel or in a
separate analysis script.

Outputs:
- seed_ie_raw_latency_time_results.csv
- seed_ie_raw_latency_time_results.json
- seed_ie_convergence_time_results.csv
- seed_ie_convergence_time_results.json
"""

import argparse
import csv
import datetime
import json
import re
import subprocess
import time
from typing import Dict, Optional

DEFAULT_ITERATIONS = 10
CONVERGENCE_ITERATIONS = 5
DEFAULT_PAUSE_BETWEEN_RUNS = 2.0

PING_COUNT = 50
PING_INTERVAL = 0.01
CMD_TIMEOUT = 90
CONVERGENCE_TIMEOUT = 60.0

LATENCY_JSON = "seed_ie_raw_latency_time_results.json"
LATENCY_CSV = "seed_ie_raw_latency_time_results.csv"
CONV_JSON = "seed_ie_convergence_time_results.json"
CONV_CSV = "seed_ie_convergence_time_results.csv"

LATENCY_PAIRS = [
    {"name": "R1-R2", "key": "r1_r2", "hops": 1, "src_container": "as100r-r1-10.0.12.254", "dst_ip": "10.0.12.253"},
    {"name": "R1-R3", "key": "r1_r3", "hops": 2, "src_container": "as100r-r1-10.0.12.254", "dst_ip": "10.0.23.253"},
    {"name": "R3-R2", "key": "r3_r2", "hops": 1, "src_container": "as100r-r3-10.0.23.253", "dst_ip": "10.0.23.254"},
    {"name": "R3-R6", "key": "r3_r6", "hops": 3, "src_container": "as100r-r3-10.0.23.253", "dst_ip": "10.0.56.253"},
    {"name": "R1-R6", "key": "r1_r6", "hops": 1, "src_container": "as100r-r1-10.0.12.254", "dst_ip": "10.0.61.253"},
    {"name": "R2-R5", "key": "r2_r5", "hops": 3, "src_container": "as100r-r2-10.0.12.253", "dst_ip": "10.0.45.253"},
    {"name": "R4-R5", "key": "r4_r5", "hops": 1, "src_container": "as100r-r4-10.0.34.253", "dst_ip": "10.0.45.253"},
    {"name": "R4-R6", "key": "r4_r6", "hops": 2, "src_container": "as100r-r4-10.0.34.253", "dst_ip": "10.0.56.253"},
    {"name": "R6-R1", "key": "r6_r1", "hops": 1, "src_container": "as100r-r6-10.0.56.253", "dst_ip": "10.0.61.254"},
]

CONVERGENCE_CONTAINER = "as100r-r3-10.0.23.253"
CONVERGENCE_DST_IP = "10.0.56.253"
FAIL_LINK_CMD_DOWN = "ip link set dev net34 down"
FAIL_LINK_CMD_UP = "ip link set dev net34 up"


def run_cmd(cmd: str, timeout: int = CMD_TIMEOUT, check: bool = True) -> str:
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=timeout)
    output = (result.stdout or "") + (result.stderr or "")
    if check and result.returncode != 0:
        raise RuntimeError(output.strip() or f"Command failed: {cmd}")
    return output


def docker_exec(container: str, command: str, timeout: int = CMD_TIMEOUT, check: bool = True) -> str:
    safe_command = command.replace('"', '\\"')
    return run_cmd(f'sudo docker exec {container} sh -lc "{safe_command}"', timeout=timeout, check=check)


def parse_single_ping(output: str) -> Dict[str, Optional[float]]:
    time_match = re.search(r"time=([\d.]+)", output)
    loss_match = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    return {
        "ping_rtt_ms": float(time_match.group(1)) if time_match else None,
        "packet_loss_pct": float(loss_match.group(1)) if loss_match else None,
        "success": time_match is not None,
    }


def timed_single_ping(container: str, dst_ip: str) -> Dict[str, Optional[float]]:
    start = time.perf_counter()
    try:
        output = docker_exec(container, f"ping -c 1 -W 1 {dst_ip}", timeout=5)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        parsed = parse_single_ping(output)
        parsed["time_module_delay_ms"] = round(elapsed_ms, 6)
        parsed["error"] = None
        return parsed
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "ping_rtt_ms": None,
            "packet_loss_pct": 100.0,
            "success": False,
            "time_module_delay_ms": round(elapsed_ms, 6),
            "error": str(exc),
        }


def run_raw_latency_tests(iterations: int, pause_s: float, latency_json: str, latency_csv: str, count: int, interval: float) -> None:
    rows = []

    for iteration in range(1, iterations + 1):
        print(f"Raw latency iteration {iteration}/{iterations}")
        iteration_started_at = datetime.datetime.now().isoformat()

        for pair in LATENCY_PAIRS:
            print(f"  Testing {pair['name']}")

            for sample_number in range(1, count + 1):
                sample_started_at = datetime.datetime.now().isoformat()
                result = timed_single_ping(pair["src_container"], pair["dst_ip"])

                rows.append({
                    "iteration": iteration,
                    "iteration_started_at": iteration_started_at,
                    "sample_timestamp": sample_started_at,
                    "pair": pair["name"],
                    "pair_key": pair["key"],
                    "hops": pair["hops"],
                    "src_container": pair["src_container"],
                    "dst_ip": pair["dst_ip"],
                    "sample_number": sample_number,
                    "success": result["success"],
                    "time_module_delay_ms": result["time_module_delay_ms"],
                    "ping_rtt_ms": result["ping_rtt_ms"],
                    "packet_loss_pct": result["packet_loss_pct"],
                    "error": result.get("error"),
                })

                if sample_number < count and interval > 0:
                    time.sleep(interval)

        if iteration < iterations and pause_s > 0:
            time.sleep(pause_s)

    payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "method": "Raw latency samples collected using Python time.perf_counter() around single ICMP ping commands. Descriptive statistics and jitter are calculated later from the raw dataset.",
        "iterations_requested": iterations,
        "iterations_completed": iterations,
        "samples_per_pair_per_iteration": count,
        "inter_sample_interval_seconds": interval,
        "pause_between_iterations_seconds": pause_s,
        "pairs": LATENCY_PAIRS,
        "raw_samples": rows,
    }

    with open(latency_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    if rows:
        with open(latency_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    print(f"Raw latency JSON saved to {latency_json}")
    print(f"Raw latency CSV saved to {latency_csv}")


def measure_convergence_once(container: str, dst_ip: str) -> Dict[str, Optional[float]]:
    docker_exec(container, FAIL_LINK_CMD_DOWN)
    start = time.perf_counter()

    failure_ms = None
    while (time.perf_counter() - start) <= CONVERGENCE_TIMEOUT:
        try:
            docker_exec(container, f"ping -c 1 -W 1 {dst_ip}", timeout=5)
            failure_ms = round((time.perf_counter() - start) * 1000.0, 3)
            break
        except Exception:
            pass

    docker_exec(container, FAIL_LINK_CMD_UP)
    start = time.perf_counter()

    recovery_ms = None
    while (time.perf_counter() - start) <= CONVERGENCE_TIMEOUT:
        try:
            docker_exec(container, f"ping -c 1 -W 1 {dst_ip}", timeout=5)
            recovery_ms = round((time.perf_counter() - start) * 1000.0, 3)
            break
        except Exception:
            pass

    return {"failure_ms": failure_ms, "recovery_ms": recovery_ms}


def run_convergence_tests(iterations: int, conv_json: str, conv_csv: str) -> None:
    rows = []
    for iteration in range(1, iterations + 1):
        print(f"Convergence iteration {iteration}/{iterations}")
        result = measure_convergence_once(CONVERGENCE_CONTAINER, CONVERGENCE_DST_IP)
        rows.append({
            "iteration": iteration,
            "timestamp": datetime.datetime.now().isoformat(),
            "failure_ms": result["failure_ms"],
            "recovery_ms": result["recovery_ms"],
        })

    payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "iterations_requested": iterations,
        "iterations_completed": len(rows),
        "raw_runs": rows,
    }

    with open(conv_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with open(conv_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["iteration", "timestamp", "failure_ms", "recovery_ms"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Convergence JSON saved to {conv_json}")
    print(f"Convergence CSV saved to {conv_csv}")


def parse_args():
    parser = argparse.ArgumentParser(description="SEED IE raw latency + convergence benchmark")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--convergence-iterations", type=int, default=CONVERGENCE_ITERATIONS)
    parser.add_argument("--count", type=int, default=PING_COUNT, help="Raw ping samples per route per iteration")
    parser.add_argument("--interval", type=float, default=PING_INTERVAL, help="Pause between single ping samples in seconds")
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE_BETWEEN_RUNS, help="Pause between iterations in seconds")
    parser.add_argument("--latency-json", default=LATENCY_JSON)
    parser.add_argument("--latency-csv", default=LATENCY_CSV)
    parser.add_argument("--conv-json", default=CONV_JSON)
    parser.add_argument("--conv-csv", default=CONV_CSV)
    parser.add_argument("--skip-latency", action="store_true", help="Only run convergence")
    parser.add_argument("--skip-convergence", action="store_true", help="Only run raw latency")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if not args.skip_latency:
        run_raw_latency_tests(
            iterations=args.iterations,
            pause_s=args.pause,
            latency_json=args.latency_json,
            latency_csv=args.latency_csv,
            count=args.count,
            interval=args.interval,
        )

    if not args.skip_convergence:
        run_convergence_tests(args.convergence_iterations, args.conv_json, args.conv_csv)
