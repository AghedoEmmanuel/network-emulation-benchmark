#!/usr/bin/env python3
"""
Dissertation Benchmark Script - Traditional Routing Side (SEED IE / OSPF / FRRouting)
Lewis-aligned version
=====================================================================================
Operational definitions aligned as closely as practical with Golightly et al. (2023):
  - Latency         : ping RTT summary values stored in seconds
  - Jitter          : mean absolute deviation of ping RTT samples from average RTT, in seconds
  - Packet loss     : ping packet loss percentage
  - Bandwidth       : sender-side iperf3 TCP rate (operational proxy, Mbps / bps)
  - Throughput      : receiver-side iperf3 TCP rate (Mbps / bps)
  - OSPF convergence: link-down/link-up recovery times in seconds
  - CPU utilisation : per-container via docker stats, sampled repeatedly to avoid zero-only snapshots
  - Memory usage    : per-container via docker stats
"""

import argparse
import csv
import json
import re
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime
from statistics import mean, stdev
from typing import Dict, List, Optional, Tuple

DEFAULT_ITERATIONS = 1000
DEFAULT_CONVERGENCE_ITERATIONS = 30
CSV_FILE = "ospf_benchmark_results_lewis.csv"

SRC_CONTAINER = "as100r-r1-10.0.12.254"
DST_CONTAINER = "as100r-r4-10.0.34.253"
DST_IP = "10.0.34.253"
FAILURE_CONTAINER = "as100r-r3-10.0.23.253"
FAILURE_INTERFACE = "net34"

PING_COUNT = 100
PING_TIMEOUT_SEC = 2
IPERF_TCP_DURATION = 10
CONVERGENCE_POLL_INTERVAL = 0.5
CONVERGENCE_TIMEOUT = 60

RESOURCE_CONTAINERS = [
    "as100r-r1-10.0.12.254",
    "as100r-r2-10.0.12.253",
    "as100r-r3-10.0.23.253",
    "as100r-r4-10.0.34.253",
    "as100r-r5-10.0.45.253",
    "as100r-r6-10.0.56.253",
]

RESOURCE_SAMPLE_COUNT = 3
RESOURCE_SAMPLE_INTERVAL = 0.5


def run_cmd(cmd: str, check: bool = True) -> str:
    result = subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed:\n{cmd}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
    return result.stdout.strip()


def docker_exec(container: str, command: str, check: bool = True) -> str:
    cmd = f"docker exec {shlex.quote(container)} sh -lc {shlex.quote(command)}"
    return run_cmd(cmd, check=check)


def container_exists(container: str) -> bool:
    try:
        run_cmd(f"docker inspect {shlex.quote(container)}", check=True)
        return True
    except Exception:
        return False


def ensure_iperf3_installed(container: str) -> None:
    try:
        docker_exec(container, "which iperf3", check=True)
    except Exception:
        raise RuntimeError(f"iperf3 is not installed in container '{container}'.")


def start_iperf3_server(container: str) -> None:
    docker_exec(container, "pkill -f 'iperf3 -s' || true", check=False)
    docker_exec(container, "nohup iperf3 -s > /tmp/iperf3_server.log 2>&1 &", check=True)
    time.sleep(1)


def stop_iperf3_server(container: str) -> None:
    docker_exec(container, "pkill -f 'iperf3 -s' || true", check=False)


def parse_ping_samples_seconds(output: str) -> List[float]:
    return [float(x) / 1000.0 for x in re.findall(r"time=([\d.]+)\s*ms", output)]


def compute_lewis_jitter(samples_s: List[float]) -> Optional[float]:
    if not samples_s:
        return None
    avg_s = sum(samples_s) / len(samples_s)
    return sum(abs(x - avg_s) for x in samples_s) / len(samples_s)


def parse_ping_output(output: str) -> Dict[str, Optional[float]]:
    packet_loss = None
    min_rtt = avg_rtt = max_rtt = std_rtt = None

    loss_match = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    if loss_match:
        packet_loss = float(loss_match.group(1))

    rtt_match = re.search(
        r"rtt min/avg/max/(?:mdev|stddev) = (\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?) ms",
        output,
    )
    if rtt_match:
        min_rtt = float(rtt_match.group(1)) / 1000.0
        avg_rtt = float(rtt_match.group(2)) / 1000.0
        max_rtt = float(rtt_match.group(3)) / 1000.0
        std_rtt = float(rtt_match.group(4)) / 1000.0

    samples_s = parse_ping_samples_seconds(output)
    jitter_s = compute_lewis_jitter(samples_s)

    return {
        "latency_min_s": min_rtt,
        "latency_avg_s": avg_rtt,
        "latency_max_s": max_rtt,
        "latency_std_s": std_rtt,
        "jitter_s": jitter_s,
        "packet_loss_percent": packet_loss,
        "sample_count": len(samples_s),
    }


def run_ping(container: str, dst_ip: str, count: int = PING_COUNT, timeout: int = PING_TIMEOUT_SEC) -> Dict[str, Optional[float]]:
    cmd = f"ping -c {count} -W {timeout} {dst_ip}"
    output = docker_exec(container, cmd, check=False)
    return parse_ping_output(output)


def run_iperf3_tcp(src_container: str, dst_ip: str, duration: int = IPERF_TCP_DURATION) -> Dict[str, Optional[float]]:
    cmd = f"iperf3 -c {dst_ip} -t {duration} -J"
    output = docker_exec(src_container, cmd, check=True)
    data = json.loads(output)
    sender_bps = float(data["end"]["sum_sent"]["bits_per_second"])
    receiver_bps = float(data["end"]["sum_received"]["bits_per_second"])
    retransmits = data["end"]["sum_sent"].get("retransmits")
    return {
        "bandwidth_bps": sender_bps,
        "bandwidth_mbps": sender_bps / 1_000_000,
        "throughput_bps": receiver_bps,
        "throughput_mbps": receiver_bps / 1_000_000,
        "tcp_retransmits": retransmits,
    }


def parse_cpu_percent(cpu_str: str) -> Optional[float]:
    match = re.match(r"(\d+(?:\.\d+)?)%", cpu_str.strip())
    return float(match.group(1)) if match else None


def parse_mem_usage(mem_str: str) -> Tuple[Optional[float], Optional[float]]:
    def to_mib(value: float, unit: str) -> float:
        unit = unit.lower()
        if unit in ("kib", "kb"):
            return value / 1024
        if unit in ("mib", "mb"):
            return value
        if unit in ("gib", "gb"):
            return value * 1024
        if unit == "b":
            return value / (1024 * 1024)
        raise ValueError(f"Unsupported unit: {unit}")

    match = re.match(r"(\d+(?:\.\d+)?)([KMG]i?B|B)\s*/\s*(\d+(?:\.\d+)?)([KMG]i?B|B)", mem_str.strip(), re.IGNORECASE)
    if not match:
        return None, None
    used_val, used_unit, lim_val, lim_unit = match.groups()
    return to_mib(float(used_val), used_unit), to_mib(float(lim_val), lim_unit)


def get_docker_stats(container: str) -> Dict[str, Optional[float]]:
    fmt = "{{.CPUPerc}},{{.MemUsage}}"
    output = run_cmd(f"docker stats --no-stream --format '{fmt}' {shlex.quote(container)}", check=True)
    parts = output.split(",", 1)
    if len(parts) != 2:
        return {"cpu_percent": None, "mem_used_mib": None, "mem_limit_mib": None, "mem_percent": None}
    cpu_str, mem_str = parts
    cpu_percent = parse_cpu_percent(cpu_str)
    mem_used_mib, mem_limit_mib = parse_mem_usage(mem_str)
    mem_percent = None
    if mem_used_mib is not None and mem_limit_mib not in (None, 0):
        mem_percent = (mem_used_mib / mem_limit_mib) * 100.0
    return {
        "cpu_percent": cpu_percent,
        "mem_used_mib": mem_used_mib,
        "mem_limit_mib": mem_limit_mib,
        "mem_percent": mem_percent,
    }


def aggregate_resource_stats(containers: List[str], samples: int = RESOURCE_SAMPLE_COUNT, interval_s: float = RESOURCE_SAMPLE_INTERVAL) -> Dict[str, Optional[float]]:
    per_sample_cpu_avg = []
    per_sample_cpu_max = []
    per_sample_mem_avg_used = []
    per_sample_mem_max_used = []
    per_sample_mem_avg_pct = []
    per_sample_mem_max_pct = []

    for sample_index in range(samples):
        cpu_values, mem_used_values, mem_percent_values = [], [], []
        for container in containers:
            if not container_exists(container):
                continue
            stats = get_docker_stats(container)
            if stats["cpu_percent"] is not None:
                cpu_values.append(stats["cpu_percent"])
            if stats["mem_used_mib"] is not None:
                mem_used_values.append(stats["mem_used_mib"])
            if stats["mem_percent"] is not None:
                mem_percent_values.append(stats["mem_percent"])

        if cpu_values:
            per_sample_cpu_avg.append(sum(cpu_values) / len(cpu_values))
            per_sample_cpu_max.append(max(cpu_values))
        if mem_used_values:
            per_sample_mem_avg_used.append(sum(mem_used_values) / len(mem_used_values))
            per_sample_mem_max_used.append(max(mem_used_values))
        if mem_percent_values:
            per_sample_mem_avg_pct.append(sum(mem_percent_values) / len(mem_percent_values))
            per_sample_mem_max_pct.append(max(mem_percent_values))

        if sample_index < samples - 1:
            time.sleep(interval_s)

    def avg(values: List[float]) -> Optional[float]:
        return round(sum(values) / len(values), 4) if values else None

    def mx(values: List[float]) -> Optional[float]:
        return round(max(values), 4) if values else None

    return {
        "cpu_avg_percent": avg(per_sample_cpu_avg),
        "cpu_max_percent": mx(per_sample_cpu_max),
        "mem_avg_used_mib": avg(per_sample_mem_avg_used),
        "mem_max_used_mib": mx(per_sample_mem_max_used),
        "mem_avg_percent": avg(per_sample_mem_avg_pct),
        "mem_max_percent": mx(per_sample_mem_max_pct),
        "resource_sample_count": samples,
        "resource_sample_interval_s": interval_s,
    }


def ping_once_success(container: str, dst_ip: str) -> bool:
    result = docker_exec(container, f"ping -c 1 -W 1 {dst_ip}", check=False)
    return "1 received" in result or "0% packet loss" in result


def measure_convergence_once(verbose: bool = True) -> dict:
    if verbose:
        print(f"  Checking baseline: {SRC_CONTAINER} -> {DST_IP} ...")
    if not ping_once_success(SRC_CONTAINER, DST_IP):
        if verbose:
            print("  ERROR: Baseline ping failed — skipping this run.")
        return {"failure_s": None, "recovery_s": None}

    if verbose:
        print(f"  Bringing {FAILURE_INTERFACE} DOWN on {FAILURE_CONTAINER} — starting failure timer ...")
    failure_start = time.time()
    docker_exec(FAILURE_CONTAINER, f"ip link set dev {FAILURE_INTERFACE} down", check=True)

    failure_s = None
    deadline = failure_start + CONVERGENCE_TIMEOUT
    while time.time() < deadline:
        if ping_once_success(SRC_CONTAINER, DST_IP):
            failure_s = round(time.time() - failure_start, 4)
            break
        time.sleep(CONVERGENCE_POLL_INTERVAL)

    if verbose:
        print(f"  Failure convergence : {failure_s:.4f} s" if failure_s is not None else f"  Failure convergence : TIMEOUT (>{CONVERGENCE_TIMEOUT} s)")

    time.sleep(1.0)

    if verbose:
        print(f"  Bringing {FAILURE_INTERFACE} UP on {FAILURE_CONTAINER} — starting recovery timer ...")
    recovery_start = time.time()
    docker_exec(FAILURE_CONTAINER, f"ip link set dev {FAILURE_INTERFACE} up", check=True)

    recovery_s = None
    deadline = recovery_start + CONVERGENCE_TIMEOUT
    while time.time() < deadline:
        if ping_once_success(SRC_CONTAINER, DST_IP):
            recovery_s = round(time.time() - recovery_start, 4)
            break
        time.sleep(CONVERGENCE_POLL_INTERVAL)

    if verbose:
        print(f"  Recovery convergence: {recovery_s:.4f} s" if recovery_s is not None else f"  Recovery convergence: TIMEOUT (>{CONVERGENCE_TIMEOUT} s)")

    time.sleep(2.0)
    return {"failure_s": failure_s, "recovery_s": recovery_s}


def run_convergence_phase(iterations: int, verbose: bool = True) -> dict:
    print(f"\n{'=' * 70}")
    print(f"  PHASE 2 — OSPF CONVERGENCE ({iterations} iterations)")
    print(f"{'=' * 70}")
    print(f"  Failure container : {FAILURE_CONTAINER}")
    print(f"  Failure interface : {FAILURE_INTERFACE}")
    print(f"  Probe             : {SRC_CONTAINER} -> {DST_IP}\n")

    results = []
    for i in range(iterations):
        if verbose:
            print(f"  --- Convergence run {i + 1}/{iterations} ---")
        val = measure_convergence_once(verbose=verbose)
        results.append(val)
        if verbose:
            print()

    failure_vals = [r["failure_s"] for r in results if r["failure_s"] is not None]
    recovery_vals = [r["recovery_s"] for r in results if r["recovery_s"] is not None]

    def summarise(vals):
        if not vals:
            return {"mean_s": None, "min_s": None, "max_s": None, "stdev_s": None, "successful_runs": 0}
        return {
            "mean_s": round(mean(vals), 4),
            "min_s": min(vals),
            "max_s": max(vals),
            "stdev_s": round(stdev(vals), 4) if len(vals) > 1 else 0.0,
            "successful_runs": len(vals),
        }

    summary = {
        "method": "link_down_up_poll",
        "failure_container": FAILURE_CONTAINER,
        "failure_interface": FAILURE_INTERFACE,
        "probe_src": SRC_CONTAINER,
        "probe_dst": DST_IP,
        "iterations": iterations,
        "failure_convergence": summarise(failure_vals),
        "recovery_convergence": summarise(recovery_vals),
        "raw_results_s": results,
    }
    print("  CONVERGENCE SUMMARY:")
    print(json.dumps({k: v for k, v in summary.items() if k != "raw_results_s"}, indent=4))
    return summary


def validate_setup() -> None:
    required = [SRC_CONTAINER, DST_CONTAINER, FAILURE_CONTAINER] + RESOURCE_CONTAINERS
    missing = [c for c in set(required) if not container_exists(c)]
    if missing:
        raise RuntimeError("These containers do not exist:\n" + "\n".join(missing) + '\n\nRun `docker ps --format "{{.Names}}"` and update the config.')
    ensure_iperf3_installed(SRC_CONTAINER)
    ensure_iperf3_installed(DST_CONTAINER)


def benchmark(iterations: int, convergence_iterations: int, skip_convergence: bool) -> None:
    validate_setup()
    start_iperf3_server(DST_CONTAINER)

    fieldnames = [
        "timestamp", "iteration", "src_container", "dst_container", "dst_ip",
        "latency_min_s", "latency_avg_s", "latency_max_s", "latency_std_s", "jitter_s", "packet_loss_percent",
        "bandwidth_bps", "bandwidth_mbps", "throughput_bps", "throughput_mbps", "tcp_retransmits",
        "cpu_avg_percent", "cpu_max_percent",
        "mem_avg_used_mib", "mem_max_used_mib", "mem_avg_percent", "mem_max_percent",
        "resource_sample_count", "resource_sample_interval_s",
    ]

    print(f"\n{'=' * 70}")
    print(f"  PHASE 1 — STEADY-STATE PERFORMANCE ({iterations} iterations)")
    print(f"{'=' * 70}\n")

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i in range(1, iterations + 1):
            print(f"[{i}/{iterations}] Running tests...")
            row = {
                "timestamp": datetime.utcnow().isoformat(),
                "iteration": i,
                "src_container": SRC_CONTAINER,
                "dst_container": DST_CONTAINER,
                "dst_ip": DST_IP,
            }

            try:
                row.update(run_ping(SRC_CONTAINER, DST_IP, count=PING_COUNT, timeout=PING_TIMEOUT_SEC))
            except Exception as e:
                print(f"  Ping failed on iteration {i}: {e}")
                row.update({
                    "latency_min_s": None, "latency_avg_s": None, "latency_max_s": None,
                    "latency_std_s": None, "jitter_s": None, "packet_loss_percent": None,
                })

            try:
                row.update(run_iperf3_tcp(SRC_CONTAINER, DST_IP, duration=IPERF_TCP_DURATION))
            except Exception as e:
                print(f"  TCP iperf3 failed on iteration {i}: {e}")
                row.update({
                    "bandwidth_bps": None, "bandwidth_mbps": None,
                    "throughput_bps": None, "throughput_mbps": None,
                    "tcp_retransmits": None,
                })

            try:
                row.update(aggregate_resource_stats(RESOURCE_CONTAINERS))
            except Exception as e:
                print(f"  Resource sampling failed on iteration {i}: {e}")
                row.update({
                    "cpu_avg_percent": None, "cpu_max_percent": None,
                    "mem_avg_used_mib": None, "mem_max_used_mib": None,
                    "mem_avg_percent": None, "mem_max_percent": None,
                    "resource_sample_count": None, "resource_sample_interval_s": None,
                })

            writer.writerow(row)
            f.flush()

    stop_iperf3_server(DST_CONTAINER)
    print(f"\nPhase 1 complete. Results written to {CSV_FILE}")

    if not skip_convergence:
        conv_summary = run_convergence_phase(convergence_iterations, verbose=True)
        conv_file = CSV_FILE.replace(".csv", "_convergence.json")
        with open(conv_file, "w", encoding="utf-8") as cf:
            json.dump(conv_summary, cf, indent=2)
        print(f"Convergence summary saved to {conv_file}")
    else:
        print("\nConvergence phase skipped (--skip-convergence).")


def parse_args():
    parser = argparse.ArgumentParser(description="SEED IE / OSPF benchmark runner for dissertation (Lewis-aligned)")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--convergence-iterations", type=int, default=DEFAULT_CONVERGENCE_ITERATIONS)
    parser.add_argument("--skip-convergence", action="store_true")
    return parser.parse_args()


def handle_sigint(sig, frame):
    print("\nInterrupted. Exiting.")
    try:
        stop_iperf3_server(DST_CONTAINER)
    except Exception:
        pass
    sys.exit(1)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)
    args = parse_args()
    benchmark(iterations=args.iterations, convergence_iterations=args.convergence_iterations, skip_convergence=args.skip_convergence)
