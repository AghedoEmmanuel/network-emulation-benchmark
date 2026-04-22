#!/usr/bin/env python3
"""
Mininet OSPF benchmark script for a 6-router FRRouting ring.

Aligned to the user's current Mininet topology:
- r1-r6 router namespaces
- /30 point-to-point links
- /32 loopbacks
- FRRouting zebra + ospfd
- OSPF convergence via router-link failure/recovery

Metrics:
- latency (min/avg/max/std/median) in ms
- jitter (mean absolute deviation from average RTT) in ms
- packet loss (%)
- throughput (iperf3 TCP receiver-side Mbps)
- bandwidth (iperf3 UDP receiver-side Mbps, operational proxy for capacity ceiling)
- CPU utilisation (% via /proc/stat on host)
- memory utilisation (% via /proc/meminfo on host)
- OSPF convergence failure/recovery (ms)

Outputs:
- mininet_ospf_benchmark_results_iterative_ms.json
- mininet_ospf_benchmark_results_iterative_ms.csv
- mininet_ospf_benchmark_results_iterative_ms_convergence.json
- mininet_ospf_benchmark_results_iterative_ms_convergence.csv

How to use:
1. Start the Mininet OSPF topology in one terminal:
       sudo python3 mininet_ospf_topology_fixed.py
2. Leave it running at the Mininet CLI.
3. In another terminal, run:
       sudo python3 benchmark_mininet_ospf.py

Notes:
- This script discovers Mininet router PIDs with `pgrep -f 'mininet:r1'` etc.
- It uses router loopbacks as test destinations so paths reflect OSPF forwarding.
- iperf3 must be installed on the Ubuntu host.
"""

import argparse
import csv
import datetime
import json
import re
import statistics
import subprocess
import sys
import time
from typing import Dict, List, Optional

# ----------------------------
# Global configuration
# ----------------------------

PING_COUNT = 100
PING_INTERVAL = 0.1
PACKET_LOSS_COUNT = 200
PACKET_LOSS_INTERVAL = 0.05
IPERF_DURATION = 10

DEFAULT_ITERATIONS = 100
DEFAULT_CONVERGENCE_ITERATIONS = 30
DEFAULT_PAUSE_BETWEEN_RUNS = 2.0
CMD_TIMEOUT = 120

DEFAULT_RESULTS_FILE = "mininet_ospf_benchmark_results_iterative_ms.json"
CONV_CSV = "mininet_ospf_benchmark_results_iterative_ms_convergence.csv"
CONV_JSON = "mininet_ospf_benchmark_results_iterative_ms_convergence.json"

ROUTERS = ["r1", "r2", "r3", "r4", "r5", "r6"]

LOOPBACKS = {
    "r1": "192.168.1.1",
    "r2": "192.168.2.1",
    "r3": "192.168.3.1",
    "r4": "192.168.4.1",
    "r5": "192.168.5.1",
    "r6": "192.168.6.1",
}

# Expanded path coverage requested by user
# Keep the same pairs for latency/jitter and packet loss.
LATENCY_PAIRS = [
    ("r1", "r2"),
    ("r1", "r3"),
    ("r3", "r2"),
    ("r3", "r6"),
    ("r1", "r6"),
    ("r2", "r5"),
    ("r4", "r5"),
    ("r4", "r6"),
    ("r6", "r1"),
]

# Use the same pairs for bandwidth and throughput for methodological consistency.
BW_TPUT_PAIRS = LATENCY_PAIRS[:]
LOSS_PAIRS = LATENCY_PAIRS[:]

# Shortest-path hops in the 6-router ring:
# r1-r2-r3-r4-r5-r6-r1
HOP_COUNTS = {
    "r1_to_r2": 1,
    "r1_to_r3": 2,
    "r3_to_r2": 1,
    "r3_to_r6": 3,
    "r1_to_r6": 1,
    "r2_to_r5": 3,
    "r4_to_r5": 1,
    "r4_to_r6": 2,
    "r6_to_r1": 1,
}

# Convergence test:
# Fail one ring link and probe end-to-end reachability to a routed loopback.
# In the topology links are created in order:
#   r1-r2, r2-r3, r3-r4, r4-r5, r5-r6, r6-r1
# On r3, the interfaces should therefore be r3-eth0 (to r2) and r3-eth1 (to r4).
# We fail r3-eth1 so the alternate ring path is required.
CONVERGENCE_SRC = "r3"
CONVERGENCE_DST = "r6"
CONVERGENCE_FAIL_INTERFACE = "r3-eth1"
CONVERGENCE_DST_IP = LOOPBACKS[CONVERGENCE_DST]
CONVERGENCE_POLL_SEC = 0.2
CONVERGENCE_TIMEOUT = 60.0

# ----------------------------
# Utility helpers
# ----------------------------

def pair_key(src: str, dst: str) -> str:
    return f"{src}_to_{dst}"


def run_shell(command: str, timeout: int = CMD_TIMEOUT) -> str:
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(output.strip() or f"Command failed: {command}")
    return output


def run_shell_allow_fail(command: str, timeout: int = CMD_TIMEOUT) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def get_router_pid(router: str) -> Optional[str]:
    # Matches Mininet host processes like "mininet:r1"
    output = run_shell_allow_fail(f"pgrep -f 'mininet:{router}' | head -1", timeout=10).strip()
    if not output or output == "TIMEOUT":
        return None
    return output


def run_mn_cmd(router: str, cmd: str, timeout: int = CMD_TIMEOUT) -> str:
    pid = get_router_pid(router)
    if not pid:
        raise RuntimeError(f"Could not find Mininet PID for router {router}")
    return run_shell(f"mnexec -a {pid} {cmd}", timeout=timeout)


def validate_environment() -> List[str]:
    issues = []
    for router in ROUTERS:
        if not get_router_pid(router):
            issues.append(f"Router process not found for {router}")

    for binary in ("mnexec", "iperf3", "ping"):
        path = run_shell_allow_fail(f"command -v {binary}", timeout=10).strip()
        if not path:
            issues.append(f"Required command not found: {binary}")

    return issues

# ----------------------------
# Host resource measurement
# ----------------------------

def _read_cpu_times() -> Dict[str, int]:
    with open("/proc/stat", "r", encoding="utf-8") as f:
        first = f.readline().strip().split()

    if first[0] != "cpu":
        raise RuntimeError("Unable to read CPU statistics from /proc/stat")

    values = list(map(int, first[1:]))
    total = sum(values)
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    user = values[0] + (values[1] if len(values) > 1 else 0)
    system = values[2] + (values[5] if len(values) > 5 else 0) + (values[6] if len(values) > 6 else 0)

    return {"total": total, "idle": idle, "user": user, "system": system}


def measure_cpu_utilisation(duration_s: float = 2.0) -> Dict[str, float]:
    start = _read_cpu_times()
    time.sleep(duration_s)
    end = _read_cpu_times()

    delta_total = end["total"] - start["total"]
    delta_idle = end["idle"] - start["idle"]
    delta_user = end["user"] - start["user"]
    delta_system = end["system"] - start["system"]

    if delta_total <= 0:
        return {
            "cpu_user_pct": 0.0,
            "cpu_system_pct": 0.0,
            "cpu_total_busy_pct": 0.0,
            "cpu_sample_window_ms": round(duration_s * 1000.0, 3),
        }

    return {
        "cpu_user_pct": round(100.0 * delta_user / delta_total, 3),
        "cpu_system_pct": round(100.0 * delta_system / delta_total, 3),
        "cpu_total_busy_pct": round(100.0 * (delta_total - delta_idle) / delta_total, 3),
        "cpu_sample_window_ms": round(duration_s * 1000.0, 3),
    }


def measure_memory_utilisation() -> Dict[str, float]:
    meminfo = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
            key, value = line.split(":", 1)
            meminfo[key.strip()] = int(value.strip().split()[0])

    total_kb = meminfo.get("MemTotal", 0)
    available_kb = meminfo.get("MemAvailable", 0)
    used_kb = max(total_kb - available_kb, 0)
    util_pct = (100.0 * used_kb / total_kb) if total_kb else 0.0

    return {
        "mem_used_mb": round(used_kb / 1024.0, 3),
        "mem_total_mb": round(total_kb / 1024.0, 3),
        "mem_utilisation_pct": round(util_pct, 3),
    }

# ----------------------------
# Ping parsing and metrics
# ----------------------------

def parse_ping_output(output: str) -> Optional[Dict[str, float]]:
    lines = output.splitlines()
    stats_line = next((l for l in lines if "min/avg/max" in l or "rtt min/avg/max" in l), None)
    if not stats_line:
        return None

    stats_match = re.search(
        r'=\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)',
        stats_line
    )
    if not stats_match:
        raise RuntimeError(f"Could not parse ping summary line: {stats_line}")

    min_rtt, avg_rtt, max_rtt, stddev = map(float, stats_match.groups())

    samples = []
    for line in lines:
        match = re.search(r"time=([\d.]+)", line)
        if match:
            samples.append(float(match.group(1)))

    loss_match = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    txrx_match = re.search(r"(\d+)\s+packets transmitted,\s+(\d+)\s+(?:packets )?received", output)

    packet_loss_pct = float(loss_match.group(1)) if loss_match else None
    packets_transmitted = int(txrx_match.group(1)) if txrx_match else None
    packets_received = int(txrx_match.group(2)) if txrx_match else None
    median_rtt = statistics.median(samples) if samples else None
    jitter = statistics.mean(abs(x - avg_rtt) for x in samples) if samples else None

    return {
        "latency_min_ms": min_rtt,
        "latency_avg_ms": avg_rtt,
        "latency_max_ms": max_rtt,
        "latency_std_ms": stddev,
        "latency_median_ms": median_rtt,
        "jitter_ms": jitter,
        "latency_loss_pct": packet_loss_pct,
        "packets_transmitted": packets_transmitted,
        "packets_received": packets_received,
        "sample_count": len(samples),
    }


def run_ping_metrics(src_router: str, dst_router: str, count: int, interval: float, timeout: int = CMD_TIMEOUT) -> Dict[str, float]:
    dst_ip = LOOPBACKS[dst_router]
    output = run_mn_cmd(src_router, f"ping -c {count} -i {interval} {dst_ip}", timeout=timeout)
    parsed = parse_ping_output(output)
    if not parsed:
        raise RuntimeError(f"Could not parse ping output for {src_router} -> {dst_router} ({dst_ip})")
    parsed["hop_count"] = HOP_COUNTS.get(pair_key(src_router, dst_router))
    return parsed

# ----------------------------
# iperf3 metrics
# ----------------------------

def cleanup_iperf_on_router(router: str) -> None:
    try:
        run_mn_cmd(router, "pkill -f iperf3 || true", timeout=15)
    except Exception:
        pass


def run_iperf_tcp_metrics(src_router: str, dst_router: str, duration: int = IPERF_DURATION) -> Dict[str, float]:
    """
    TCP:
    - bandwidth proxy: sender-side achieved TCP rate
    - throughput: receiver-side achieved TCP rate
    """
    dst_ip = LOOPBACKS[dst_router]

    cleanup_iperf_on_router(dst_router)
    cleanup_iperf_on_router(src_router)

    run_mn_cmd(dst_router, "nohup iperf3 -s >/tmp/iperf3_server.log 2>&1 &", timeout=15)
    time.sleep(1.0)

    try:
        output = run_mn_cmd(src_router, f"iperf3 -c {dst_ip} -t {duration} -J", timeout=duration + 30)
        data = json.loads(output)
        end = data.get("end", {})
        sent = end.get("sum_sent", {})
        received = end.get("sum_received", {})

        bandwidth_bps = float(sent.get("bits_per_second", 0.0))
        throughput_bps = float(received.get("bits_per_second", 0.0))
        retransmits = int(sent.get("retransmits", 0)) if sent.get("retransmits") is not None else 0

        return {
            "bandwidth_mbps": round(bandwidth_bps / 1_000_000.0, 6),
            "throughput_mbps": round(throughput_bps / 1_000_000.0, 6),
            "retransmits": retransmits,
        }
    finally:
        cleanup_iperf_on_router(dst_router)
        cleanup_iperf_on_router(src_router)


def run_iperf_udp_bandwidth_metrics(src_router: str, dst_router: str, duration: int = IPERF_DURATION, target_bitrate: str = "1G") -> Dict[str, float]:
    """
    UDP operational bandwidth test.
    Uses receiver-side Mbps as the main delivered-rate figure.
    """
    dst_ip = LOOPBACKS[dst_router]

    cleanup_iperf_on_router(dst_router)
    cleanup_iperf_on_router(src_router)

    run_mn_cmd(dst_router, "nohup iperf3 -s >/tmp/iperf3_server.log 2>&1 &", timeout=15)
    time.sleep(1.0)

    try:
        output = run_mn_cmd(
            src_router,
            f"iperf3 -u -c {dst_ip} -b {target_bitrate} -t {duration} -J",
            timeout=duration + 30,
        )
        data = json.loads(output)
        end = data.get("end", {})
        sum_result = end.get("sum", {}) or end.get("sum_received", {}) or {}

        delivered_bps = float(sum_result.get("bits_per_second", 0.0))
        jitter_ms = float(sum_result.get("jitter_ms", 0.0)) if sum_result.get("jitter_ms") is not None else 0.0
        lost_packets = int(sum_result.get("lost_packets", 0)) if sum_result.get("lost_packets") is not None else 0
        packets = int(sum_result.get("packets", 0)) if sum_result.get("packets") is not None else 0
        loss_pct = float(sum_result.get("lost_percent", 0.0)) if sum_result.get("lost_percent") is not None else 0.0

        return {
            "udp_bandwidth_mbps": round(delivered_bps / 1_000_000.0, 6),
            "udp_jitter_ms": round(jitter_ms, 6),
            "udp_lost_packets": lost_packets,
            "udp_total_packets": packets,
            "udp_loss_pct": round(loss_pct, 6),
        }
    finally:
        cleanup_iperf_on_router(dst_router)
        cleanup_iperf_on_router(src_router)

# ----------------------------
# Summary helpers
# ----------------------------

def compute_numeric_summary(values: List[float]) -> Dict[str, Optional[float]]:
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


def build_empty_row(iteration: int, started_at: str) -> Dict[str, Optional[float]]:
    row = {
        "iteration": iteration,
        "started_at": started_at,
        "completed_at": None,
        "duration_ms": None,
    }

    for src, dst in LATENCY_PAIRS:
        k = f"{src}_{dst}"
        row[f"latency_{k}_hops"] = HOP_COUNTS.get(pair_key(src, dst))
        row[f"latency_{k}_min_ms"] = None
        row[f"latency_{k}_avg_ms"] = None
        row[f"latency_{k}_max_ms"] = None
        row[f"latency_{k}_std_ms"] = None
        row[f"latency_{k}_median_ms"] = None
        row[f"jitter_{k}_ms"] = None
        row[f"latency_{k}_loss_pct"] = None

    for src, dst in BW_TPUT_PAIRS:
        k = f"{src}_{dst}"
        row[f"bandwidth_{k}_mbps"] = None
        row[f"throughput_{k}_mbps"] = None
        row[f"retransmits_{k}"] = None
        row[f"udp_bandwidth_{k}_mbps"] = None
        row[f"udp_jitter_{k}_ms"] = None
        row[f"udp_loss_{k}_pct"] = None

    for src, dst in LOSS_PAIRS:
        k = f"{src}_{dst}"
        row[f"packetloss_{k}_pct"] = None

    row["cpu_total_busy_pct"] = None
    row["cpu_user_pct"] = None
    row["cpu_system_pct"] = None
    row["cpu_sample_window_ms"] = None
    row["mem_used_mb"] = None
    row["mem_total_mb"] = None
    row["mem_utilisation_pct"] = None
    return row

# ----------------------------
# Steady-state benchmark
# ----------------------------

def run_steady_state_benchmark(
    iterations: int = DEFAULT_ITERATIONS,
    pause_s: float = DEFAULT_PAUSE_BETWEEN_RUNS,
    output_file: str = DEFAULT_RESULTS_FILE
) -> None:
    raw_runs = []
    csv_rows = []

    for i in range(1, iterations + 1):
        started_at = datetime.datetime.now().isoformat()
        print(f"Steady-state iteration {i}/{iterations}")
        iteration_start = time.time()

        run_record = {
            "iteration": i,
            "started_at": started_at,
            "completed_at": None,
            "latency_jitter": {},
            "bandwidth_throughput": {},
            "udp_bandwidth": {},
            "packet_loss": {},
        }
        csv_row = build_empty_row(i, started_at)

        # latency + jitter
        for src, dst in LATENCY_PAIRS:
            pair_name = f"{src.upper()}-{dst.upper()}"
            try:
                res = run_ping_metrics(src, dst, count=PING_COUNT, interval=PING_INTERVAL)
                run_record["latency_jitter"][pair_name] = res
                k = f"{src}_{dst}"
                csv_row[f"latency_{k}_min_ms"] = res.get("latency_min_ms")
                csv_row[f"latency_{k}_avg_ms"] = res.get("latency_avg_ms")
                csv_row[f"latency_{k}_max_ms"] = res.get("latency_max_ms")
                csv_row[f"latency_{k}_std_ms"] = res.get("latency_std_ms")
                csv_row[f"latency_{k}_median_ms"] = res.get("latency_median_ms")
                csv_row[f"jitter_{k}_ms"] = res.get("jitter_ms")
                csv_row[f"latency_{k}_loss_pct"] = res.get("latency_loss_pct")
            except Exception as e:
                run_record["latency_jitter"][pair_name] = {
                    "error": str(e),
                    "hop_count": HOP_COUNTS.get(pair_key(src, dst)),
                }

        # TCP throughput + sender-side bandwidth proxy
        for src, dst in BW_TPUT_PAIRS:
            pair_name = f"{src.upper()}-{dst.upper()}"
            try:
                res = run_iperf_tcp_metrics(src, dst, duration=IPERF_DURATION)
                res["hop_count"] = HOP_COUNTS.get(pair_key(src, dst))
                run_record["bandwidth_throughput"][pair_name] = res
                k = f"{src}_{dst}"
                csv_row[f"bandwidth_{k}_mbps"] = res.get("bandwidth_mbps")
                csv_row[f"throughput_{k}_mbps"] = res.get("throughput_mbps")
                csv_row[f"retransmits_{k}"] = res.get("retransmits")
            except Exception as e:
                run_record["bandwidth_throughput"][pair_name] = {
                    "error": str(e),
                    "hop_count": HOP_COUNTS.get(pair_key(src, dst)),
                }

        # UDP bandwidth
        for src, dst in BW_TPUT_PAIRS:
            pair_name = f"{src.upper()}-{dst.upper()}"
            try:
                res = run_iperf_udp_bandwidth_metrics(src, dst, duration=IPERF_DURATION, target_bitrate="1G")
                res["hop_count"] = HOP_COUNTS.get(pair_key(src, dst))
                run_record["udp_bandwidth"][pair_name] = res
                k = f"{src}_{dst}"
                csv_row[f"udp_bandwidth_{k}_mbps"] = res.get("udp_bandwidth_mbps")
                csv_row[f"udp_jitter_{k}_ms"] = res.get("udp_jitter_ms")
                csv_row[f"udp_loss_{k}_pct"] = res.get("udp_loss_pct")
            except Exception as e:
                run_record["udp_bandwidth"][pair_name] = {
                    "error": str(e),
                    "hop_count": HOP_COUNTS.get(pair_key(src, dst)),
                }

        # packet loss
        for src, dst in LOSS_PAIRS:
            pair_name = f"{src.upper()}-{dst.upper()}"
            try:
                res = run_ping_metrics(src, dst, count=PACKET_LOSS_COUNT, interval=PACKET_LOSS_INTERVAL)
                loss_record = {
                    "hop_count": HOP_COUNTS.get(pair_key(src, dst)),
                    "packet_loss_pct": res.get("latency_loss_pct"),
                    "packets_transmitted": res.get("packets_transmitted"),
                    "packets_received": res.get("packets_received"),
                }
                run_record["packet_loss"][pair_name] = loss_record
                csv_row[f"packetloss_{src}_{dst}_pct"] = loss_record.get("packet_loss_pct")
            except Exception as e:
                run_record["packet_loss"][pair_name] = {
                    "error": str(e),
                    "hop_count": HOP_COUNTS.get(pair_key(src, dst)),
                }

        cpu_stats = measure_cpu_utilisation(duration_s=2.0)
        mem_stats = measure_memory_utilisation()
        completed_at = datetime.datetime.now().isoformat()
        duration_ms = round((time.time() - iteration_start) * 1000.0, 3)

        run_record["cpu_utilisation"] = cpu_stats
        run_record["memory_utilisation"] = mem_stats
        run_record["duration_ms"] = duration_ms
        run_record["completed_at"] = completed_at

        csv_row["completed_at"] = completed_at
        csv_row["duration_ms"] = duration_ms
        csv_row.update(cpu_stats)
        csv_row.update(mem_stats)

        raw_runs.append(run_record)
        csv_rows.append(csv_row)

        if i < iterations and pause_s > 0:
            time.sleep(pause_s)

    summary = {
        "latency_jitter": {},
        "bandwidth_throughput": {},
        "udp_bandwidth": {},
        "packet_loss": {},
        "cpu_total_busy_pct": compute_numeric_summary([r["cpu_utilisation"].get("cpu_total_busy_pct") for r in raw_runs]),
        "mem_utilisation_pct": compute_numeric_summary([r["memory_utilisation"].get("mem_utilisation_pct") for r in raw_runs]),
        "duration_ms": compute_numeric_summary([r.get("duration_ms") for r in raw_runs]),
    }

    for src, dst in LATENCY_PAIRS:
        name = f"{src.upper()}-{dst.upper()}"
        pair_runs = [r["latency_jitter"].get(name, {}) for r in raw_runs]
        summary["latency_jitter"][name] = {
            "hop_count": HOP_COUNTS.get(pair_key(src, dst)),
            "latency_min_ms": compute_numeric_summary([x.get("latency_min_ms") for x in pair_runs]),
            "latency_avg_ms": compute_numeric_summary([x.get("latency_avg_ms") for x in pair_runs]),
            "latency_max_ms": compute_numeric_summary([x.get("latency_max_ms") for x in pair_runs]),
            "latency_std_ms": compute_numeric_summary([x.get("latency_std_ms") for x in pair_runs]),
            "latency_median_ms": compute_numeric_summary([x.get("latency_median_ms") for x in pair_runs]),
            "jitter_ms": compute_numeric_summary([x.get("jitter_ms") for x in pair_runs]),
            "latency_loss_pct": compute_numeric_summary([x.get("latency_loss_pct") for x in pair_runs]),
        }

    for src, dst in BW_TPUT_PAIRS:
        name = f"{src.upper()}-{dst.upper()}"
        tcp_runs = [r["bandwidth_throughput"].get(name, {}) for r in raw_runs]
        udp_runs = [r["udp_bandwidth"].get(name, {}) for r in raw_runs]

        summary["bandwidth_throughput"][name] = {
            "hop_count": HOP_COUNTS.get(pair_key(src, dst)),
            "bandwidth_mbps": compute_numeric_summary([x.get("bandwidth_mbps") for x in tcp_runs]),
            "throughput_mbps": compute_numeric_summary([x.get("throughput_mbps") for x in tcp_runs]),
            "retransmits": compute_numeric_summary([x.get("retransmits") for x in tcp_runs]),
        }

        summary["udp_bandwidth"][name] = {
            "hop_count": HOP_COUNTS.get(pair_key(src, dst)),
            "udp_bandwidth_mbps": compute_numeric_summary([x.get("udp_bandwidth_mbps") for x in udp_runs]),
            "udp_jitter_ms": compute_numeric_summary([x.get("udp_jitter_ms") for x in udp_runs]),
            "udp_loss_pct": compute_numeric_summary([x.get("udp_loss_pct") for x in udp_runs]),
        }

    for src, dst in LOSS_PAIRS:
        name = f"{src.upper()}-{dst.upper()}"
        pair_runs = [r["packet_loss"].get(name, {}) for r in raw_runs]
        summary["packet_loss"][name] = {
            "hop_count": HOP_COUNTS.get(pair_key(src, dst)),
            "packet_loss_pct": compute_numeric_summary([x.get("packet_loss_pct") for x in pair_runs]),
        }

    json_payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "environment": "Mininet OSPF - FRRouting",
        "topology": "6-router ring, point-to-point /30 links, loopback /32 per router",
        "iterations_requested": iterations,
        "iterations_completed": len(raw_runs),
        "hop_counts": HOP_COUNTS,
        "metric_definition": {
            "latency": "ping RTT summary in milliseconds",
            "jitter": "mean absolute deviation of ping RTT samples from average RTT, in milliseconds",
            "latency_median": "median of individual ping RTT samples in milliseconds",
            "bandwidth": "iperf3 TCP sender-side achieved rate (operational proxy) in Mbps",
            "throughput": "iperf3 TCP receiver-side achieved rate in Mbps",
            "udp_bandwidth": "iperf3 UDP receiver-side achieved rate in Mbps",
            "convergence": "router link-down/link-up recovery time in milliseconds",
        },
        "raw_runs": raw_runs,
        "summary": summary,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, indent=2)

    if csv_rows:
        csv_file = output_file.replace(".json", ".csv")
        fieldnames = list(csv_rows[0].keys())
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

    print(f"Steady-state JSON saved to {output_file}")
    print(f"Steady-state CSV saved to {output_file.replace('.json', '.csv')}")

# ----------------------------
# Convergence benchmark
# ----------------------------

def _ping_once_success(src_router: str, dst_ip: str) -> bool:
    try:
        output = run_mn_cmd(src_router, f"ping -c 1 -W 1 {dst_ip}", timeout=5)
        return (" 0% packet loss" in output) or (", 0% packet loss" in output) or ("1 received" in output)
    except Exception:
        return False


def measure_convergence_once(src_router: str, fail_interface: str, dst_ip: str) -> Dict[str, Optional[float]]:
    # Baseline check
    if not _ping_once_success(src_router, dst_ip):
        return {"failure_ms": None, "recovery_ms": None, "error": "Baseline ping failed"}

    # Failure convergence
    run_mn_cmd(src_router, f"ip link set dev {fail_interface} down", timeout=10)
    failure_start = time.time()

    failure_ms = None
    failure_deadline = failure_start + CONVERGENCE_TIMEOUT
    while time.time() < failure_deadline:
        if _ping_once_success(src_router, dst_ip):
            failure_ms = round((time.time() - failure_start) * 1000.0, 3)
            break
        time.sleep(CONVERGENCE_POLL_SEC)

    time.sleep(1.0)

    # Recovery convergence
    run_mn_cmd(src_router, f"ip link set dev {fail_interface} up", timeout=10)
    recovery_start = time.time()

    recovery_ms = None
    recovery_deadline = recovery_start + CONVERGENCE_TIMEOUT
    while time.time() < recovery_deadline:
        if _ping_once_success(src_router, dst_ip):
            recovery_ms = round((time.time() - recovery_start) * 1000.0, 3)
            break
        time.sleep(CONVERGENCE_POLL_SEC)

    time.sleep(2.0)
    return {"failure_ms": failure_ms, "recovery_ms": recovery_ms}


def run_convergence_tests(iterations: int = DEFAULT_CONVERGENCE_ITERATIONS) -> None:
    rows = []
    for i in range(1, iterations + 1):
        print(f"Convergence iteration {i}/{iterations}")
        result = measure_convergence_once(CONVERGENCE_SRC, CONVERGENCE_FAIL_INTERFACE, CONVERGENCE_DST_IP)
        rows.append({
            "iteration": i,
            "failure_ms": result.get("failure_ms"),
            "recovery_ms": result.get("recovery_ms"),
            "error": result.get("error"),
        })

    with open(CONV_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["iteration", "failure_ms", "recovery_ms", "error"])
        writer.writeheader()
        writer.writerows(rows)

    with open(CONV_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "environment": "Mininet OSPF - FRRouting",
                "method": "router_link_down_up_poll",
                "probe_src": CONVERGENCE_SRC,
                "probe_dst_loopback": CONVERGENCE_DST_IP,
                "interface_failed": CONVERGENCE_FAIL_INTERFACE,
                "iterations_requested": iterations,
                "iterations_completed": len(rows),
                "raw_runs": rows,
                "summary": {
                    "failure_ms": compute_numeric_summary([r.get("failure_ms") for r in rows]),
                    "recovery_ms": compute_numeric_summary([r.get("recovery_ms") for r in rows]),
                },
            },
            f,
            indent=2,
        )

    print(f"Convergence CSV saved to {CONV_CSV}")
    print(f"Convergence JSON saved to {CONV_JSON}")

# ----------------------------
# CLI
# ----------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Iterative Mininet OSPF benchmark runner")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS, help="Number of steady-state iterations")
    parser.add_argument("--convergence-iterations", type=int, default=DEFAULT_CONVERGENCE_ITERATIONS, help="Number of convergence iterations")
    parser.add_argument("--skip-convergence", action="store_true", help="Skip convergence tests")
    parser.add_argument("--output", default=DEFAULT_RESULTS_FILE, help="Steady-state JSON output filename")
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE_BETWEEN_RUNS, help="Pause between steady-state iterations in seconds")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 72)
    print("MININET OSPF BENCHMARK - FRROUTING")
    print("=" * 72)
    print(f"Steady-state iterations : {args.iterations}")
    print(f"Convergence iterations  : {0 if args.skip_convergence else args.convergence_iterations}")
    print(f"Output file             : {args.output}")
    print(f"Pause between runs      : {args.pause} seconds")
    print()

    issues = validate_environment()
    if issues:
        print("Environment validation failed:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)

    run_steady_state_benchmark(
        iterations=args.iterations,
        pause_s=args.pause,
        output_file=args.output,
    )

    if not args.skip_convergence:
        run_convergence_tests(iterations=args.convergence_iterations)


if __name__ == "__main__":
    main()