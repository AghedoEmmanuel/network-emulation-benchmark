#!/usr/bin/env python3
"""
Focused latency/jitter + convergence benchmark.

This version is designed for the lecturer's instruction to use Python's time module.
It measures per-sample delay with time.perf_counter(), computes jitter as the mean
absolute difference between consecutive measured delays, and saves both CSV and JSON.

Outputs:
- steady-state latency/jitter CSV
- steady-state latency/jitter JSON
- convergence CSV
- convergence JSON
"""

import argparse
import csv
import datetime
import json
import os
import re
import shutil
import statistics
import subprocess
import time
from typing import Dict, List, Optional

DEFAULT_ITERATIONS = 10
CONVERGENCE_ITERATIONS = 5
DEFAULT_PAUSE_BETWEEN_RUNS = 2.0

PING_COUNT = 100
PING_INTERVAL = 0.1
CMD_TIMEOUT = 90
CONVERGENCE_TIMEOUT = 60.0

LATENCY_JSON = "mininet_latency_jitter_time_results.json"
LATENCY_CSV = "mininet_latency_jitter_time_results.csv"
CONV_JSON = "mininet_convergence_time_results.json"
CONV_CSV = "mininet_convergence_time_results.csv"

EXEC_MODE = "auto"

LATENCY_PAIRS = [
    {"name": "R1-R2", "key": "r1_r2", "hops": 1, "src_node": "r1", "dst_node": "r2", "dst_ip": "10.0.12.2"},
    {"name": "R1-R3", "key": "r1_r3", "hops": 2, "src_node": "r1", "dst_node": "r3", "dst_ip": "10.0.23.2"},
    {"name": "R3-R2", "key": "r3_r2", "hops": 1, "src_node": "r3", "dst_node": "r2", "dst_ip": "10.0.23.1"},
    {"name": "R3-R6", "key": "r3_r6", "hops": 3, "src_node": "r3", "dst_node": "r6", "dst_ip": "10.0.56.2"},
    {"name": "R1-R6", "key": "r1_r6", "hops": 1, "src_node": "r1", "dst_node": "r6", "dst_ip": "10.0.61.1"},
    {"name": "R2-R5", "key": "r2_r5", "hops": 3, "src_node": "r2", "dst_node": "r5", "dst_ip": "10.0.45.2"},
    {"name": "R4-R5", "key": "r4_r5", "hops": 1, "src_node": "r4", "dst_node": "r5", "dst_ip": "10.0.45.2"},
    {"name": "R4-R6", "key": "r4_r6", "hops": 2, "src_node": "r4", "dst_node": "r6", "dst_ip": "10.0.56.2"},
    {"name": "R6-R1", "key": "r6_r1", "hops": 1, "src_node": "r6", "dst_node": "r1", "dst_ip": "10.0.61.2"},
]

CONVERGENCE_NODE = "r3"
CONVERGENCE_DST_IP = "10.0.56.2"
FAIL_IFACE = "r3-eth2"
FAIL_LINK_CMD_DOWN = f"ip link set dev {FAIL_IFACE} down"
FAIL_LINK_CMD_UP = f"ip link set dev {FAIL_IFACE} up"


def run_cmd(cmd: str, timeout: int = CMD_TIMEOUT, check: bool = True) -> str:
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=timeout)
    output = (result.stdout or "") + (result.stderr or "")
    if check and result.returncode != 0:
        raise RuntimeError(output.strip() or f"Command failed: {cmd}")
    return output


def _resolve_mininet_pid(node: str) -> Optional[str]:
    patterns = [
        f"mininet:{node}$",
        f"mininet:{node} ",
        f"bash.*mininet:{node}",
        f".*{node}.*mininet",
    ]
    for pat in patterns:
        try:
            out = run_cmd(f"pgrep -f '{pat}' | head -n 1", timeout=10).strip()
            if out:
                return out
        except Exception:
            pass

    pid_file = f"/var/run/mininet/{node}.pid"
    if os.path.exists(pid_file):
        with open(pid_file, "r", encoding="utf-8") as f:
            pid = f.read().strip()
        if pid:
            return pid

    return None


def _build_node_exec_prefix(node: str) -> str:
    if EXEC_MODE in ("auto", "mnexec"):
        pid = _resolve_mininet_pid(node)
        if pid:
            return f"mnexec -a {pid}"

    if EXEC_MODE in ("auto", "ipnetns"):
        try:
            netns = run_cmd("ip netns list", timeout=10)
            if re.search(rf"^{re.escape(node)}(\s|$)", netns, flags=re.MULTILINE):
                return f"ip netns exec {node}"
        except Exception:
            pass

    raise RuntimeError(f"Could not resolve execution namespace for Mininet node '{node}'")


def node_exec(node: str, command: str, timeout: int = CMD_TIMEOUT, check: bool = True) -> str:
    safe_command = command.replace('"', '\\"')
    prefix = _build_node_exec_prefix(node)
    return run_cmd(f'{prefix} sh -lc "{safe_command}"', timeout=timeout, check=check)


def parse_single_ping(output: str) -> Dict[str, Optional[float]]:
    time_match = re.search(r"time=([\d.]+)", output)
    loss_match = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    return {
        "ping_rtt_ms": float(time_match.group(1)) if time_match else None,
        "packet_loss_pct": float(loss_match.group(1)) if loss_match else None,
        "success": time_match is not None,
    }


def timed_single_ping(node: str, dst_ip: str) -> Dict[str, Optional[float]]:
    start = time.perf_counter()
    try:
        output = node_exec(node, f"ping -c 1 -W 1 {dst_ip}", timeout=5)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        parsed = parse_single_ping(output)
        parsed["time_module_delay_ms"] = elapsed_ms
        return parsed
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "ping_rtt_ms": None,
            "packet_loss_pct": 100.0,
            "success": False,
            "time_module_delay_ms": elapsed_ms,
        }


def compute_numeric_summary(values: List[Optional[float]]) -> Dict[str, Optional[float]]:
    valid = [float(v) for v in values if v is not None]
    if not valid:
        return {"count": 0, "mean": None, "min": None, "max": None, "stdev": None, "median": None}
    return {
        "count": len(valid),
        "mean": round(statistics.mean(valid), 6),
        "min": round(min(valid), 6),
        "max": round(max(valid), 6),
        "stdev": round(statistics.stdev(valid), 6) if len(valid) > 1 else 0.0,
        "median": round(statistics.median(valid), 6),
    }


def measure_latency_jitter_time(node: str, dst_ip: str, count: int = PING_COUNT, interval: float = PING_INTERVAL) -> Dict[str, Optional[float]]:
    delays = []
    ping_rtts = []
    lost = 0

    for i in range(count):
        result = timed_single_ping(node, dst_ip)
        if result["success"]:
            delays.append(result["time_module_delay_ms"])
            ping_rtts.append(result["ping_rtt_ms"])
        else:
            lost += 1
        if i < count - 1 and interval > 0:
            time.sleep(interval)

    jitter_values = [abs(delays[i] - delays[i - 1]) for i in range(1, len(delays))]
    return {
        "samples_requested": count,
        "samples_received": len(delays),
        "packet_loss_pct": round((lost / count) * 100.0, 6) if count else None,
        "latency_min_ms": round(min(delays), 6) if delays else None,
        "latency_avg_ms": round(statistics.mean(delays), 6) if delays else None,
        "latency_max_ms": round(max(delays), 6) if delays else None,
        "latency_std_ms": round(statistics.stdev(delays), 6) if len(delays) > 1 else 0.0,
        "latency_median_ms": round(statistics.median(delays), 6) if delays else None,
        "jitter_ms": round(statistics.mean(jitter_values), 6) if jitter_values else None,
        "ping_rtt_avg_ms": round(statistics.mean(ping_rtts), 6) if ping_rtts else None,
    }


def run_latency_jitter_tests(iterations: int, pause_s: float, latency_json: str, latency_csv: str) -> None:
    rows = []
    raw_runs = []

    for iteration in range(1, iterations + 1):
        print(f"Latency/jitter iteration {iteration}/{iterations}")
        started_at = datetime.datetime.now().isoformat()
        iteration_start = time.perf_counter()
        run_record = {"iteration": iteration, "started_at": started_at, "pairs": {}}

        row = {"iteration": iteration, "started_at": started_at, "completed_at": None, "duration_ms": None}

        for pair in LATENCY_PAIRS:
            print(f"  Testing {pair['name']}")
            result = measure_latency_jitter_time(pair["src_node"], pair["dst_ip"])
            result["hops"] = pair["hops"]
            run_record["pairs"][pair["name"]] = result

            k = pair["key"]
            row[f"{k}_name"] = pair["name"]
            row[f"{k}_hops"] = pair["hops"]
            row[f"{k}_latency_min_ms"] = result["latency_min_ms"]
            row[f"{k}_latency_avg_ms"] = result["latency_avg_ms"]
            row[f"{k}_latency_max_ms"] = result["latency_max_ms"]
            row[f"{k}_latency_std_ms"] = result["latency_std_ms"]
            row[f"{k}_latency_median_ms"] = result["latency_median_ms"]
            row[f"{k}_jitter_ms"] = result["jitter_ms"]
            row[f"{k}_packet_loss_pct"] = result["packet_loss_pct"]
            row[f"{k}_samples_received"] = result["samples_received"]

        completed_at = datetime.datetime.now().isoformat()
        row["completed_at"] = completed_at
        row["duration_ms"] = round((time.perf_counter() - iteration_start) * 1000.0, 3)
        run_record["completed_at"] = completed_at
        run_record["duration_ms"] = row["duration_ms"]

        rows.append(row)
        raw_runs.append(run_record)

        if iteration < iterations and pause_s > 0:
            time.sleep(pause_s)

    summary = {}
    for pair in LATENCY_PAIRS:
        name = pair["name"]
        pair_runs = [r["pairs"].get(name, {}) for r in raw_runs]
        summary[name] = {
            "hops": pair["hops"],
            "latency_avg_ms": compute_numeric_summary([x.get("latency_avg_ms") for x in pair_runs]),
            "jitter_ms": compute_numeric_summary([x.get("jitter_ms") for x in pair_runs]),
            "packet_loss_pct": compute_numeric_summary([x.get("packet_loss_pct") for x in pair_runs]),
        }

    payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "method": "Python time.perf_counter around single ICMP ping samples; jitter is mean absolute difference between consecutive measured delays.",
        "iterations_requested": iterations,
        "iterations_completed": len(raw_runs),
        "raw_runs": raw_runs,
        "summary": summary,
    }

    with open(latency_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    if rows:
        with open(latency_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    print(f"Latency/jitter JSON saved to {latency_json}")
    print(f"Latency/jitter CSV saved to {latency_csv}")


def measure_convergence_once(node: str, dst_ip: str) -> Dict[str, Optional[float]]:
    node_exec(node, FAIL_LINK_CMD_DOWN)
    start = time.perf_counter()

    failure_ms = None
    while (time.perf_counter() - start) <= CONVERGENCE_TIMEOUT:
        try:
            node_exec(node, f"ping -c 1 -W 1 {dst_ip}", timeout=5)
            failure_ms = round((time.perf_counter() - start) * 1000.0, 3)
            break
        except Exception:
            pass

    node_exec(node, FAIL_LINK_CMD_UP)
    start = time.perf_counter()

    recovery_ms = None
    while (time.perf_counter() - start) <= CONVERGENCE_TIMEOUT:
        try:
            node_exec(node, f"ping -c 1 -W 1 {dst_ip}", timeout=5)
            recovery_ms = round((time.perf_counter() - start) * 1000.0, 3)
            break
        except Exception:
            pass

    return {"failure_ms": failure_ms, "recovery_ms": recovery_ms}


def run_convergence_tests(iterations: int, conv_json: str, conv_csv: str) -> None:
    rows = []
    for iteration in range(1, iterations + 1):
        print(f"Convergence iteration {iteration}/{iterations}")
        result = measure_convergence_once(CONVERGENCE_NODE, CONVERGENCE_DST_IP)
        rows.append({
            "iteration": iteration,
            "failure_ms": result["failure_ms"],
            "recovery_ms": result["recovery_ms"],
        })

    payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "iterations_requested": iterations,
        "iterations_completed": len(rows),
        "raw_runs": rows,
        "summary": {
            "failure_ms": compute_numeric_summary([r["failure_ms"] for r in rows]),
            "recovery_ms": compute_numeric_summary([r["recovery_ms"] for r in rows]),
        },
    }

    with open(conv_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with open(conv_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["iteration", "failure_ms", "recovery_ms"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Convergence JSON saved to {conv_json}")
    print(f"Convergence CSV saved to {conv_csv}")


def preflight_checks() -> None:
    for binary in ("ping", "mnexec", "pgrep"):
        if not shutil.which(binary):
            print(f"Warning: '{binary}' not found on host PATH")

    nodes = sorted({p["src_node"] for p in LATENCY_PAIRS} | {p["dst_node"] for p in LATENCY_PAIRS})
    for node in nodes:
        try:
            _build_node_exec_prefix(node)
        except Exception as e:
            print(f"Warning: could not resolve node '{node}': {e}")


def parse_args():
    parser = argparse.ArgumentParser(description="Mininet FRR OSPF latency/jitter + convergence benchmark")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--convergence-iterations", type=int, default=CONVERGENCE_ITERATIONS)
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE_BETWEEN_RUNS)
    parser.add_argument("--exec-mode", choices=["auto", "mnexec", "ipnetns"], default=EXEC_MODE)
    parser.add_argument("--latency-json", default=LATENCY_JSON)
    parser.add_argument("--latency-csv", default=LATENCY_CSV)
    parser.add_argument("--conv-json", default=CONV_JSON)
    parser.add_argument("--conv-csv", default=CONV_CSV)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    EXEC_MODE = args.exec_mode
    preflight_checks()
    run_latency_jitter_tests(args.iterations, args.pause, args.latency_json, args.latency_csv)
    run_convergence_tests(args.convergence_iterations, args.conv_json, args.conv_csv)
