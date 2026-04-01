#!/usr/bin/env python3
"""
OSPF benchmark script aligned with the Mininet benchmark structure.

Fixes applied:
- corrected SEED Docker container names
- corrected router destination IPs
- fixed ping summary parsing for values ending in " ms"
- added command-line arguments for test runs
"""

import argparse
import csv
import datetime
import json
import re
import statistics
import subprocess
import time
from typing import Dict, List, Optional

DEFAULT_ITERATIONS = 1000
CONVERGENCE_ITERATIONS = 30
DEFAULT_PAUSE_BETWEEN_RUNS = 2.0
CMD_TIMEOUT = 90

PING_COUNT = 100
PING_INTERVAL = 0.1
PACKET_LOSS_COUNT = 200
IPERF_DURATION = 10

DEFAULT_RESULTS_FILE = "ospf_benchmark_results_iterative_ms.json"
CONV_CSV = "ospf_benchmark_results_iterative_ms_convergence.csv"
CONV_JSON = "ospf_benchmark_results_iterative_ms_convergence.json"

LATENCY_PAIRS = [
    {
        "name": "R1-R2",
        "hops": 1,
        "src_container": "r-r1-10.0.12.254",
        "dst_container": "r-r2-10.0.12.253",
        "dst_ip": "10.0.12.253",
    },
    {
        "name": "R1-R4",
        "hops": 3,
        "src_container": "r-r1-10.0.12.254",
        "dst_container": "r-r4-10.0.34.253",
        "dst_ip": "10.0.34.253",
    },
    {
        "name": "R1-R6",
        "hops": 1,
        "src_container": "r-r1-10.0.12.254",
        "dst_container": "r-r6-10.0.56.253",
        "dst_ip": "10.0.56.253",
    },
]

BW_TPUT_PAIRS = [
    LATENCY_PAIRS[0],
    LATENCY_PAIRS[1],
]

LOSS_PAIRS = LATENCY_PAIRS[:]

CONVERGENCE_CONTAINER = "r-r3-10.0.23.253"
CONVERGENCE_DST_IP = "10.0.56.253"
FAIL_LINK_CMD_DOWN = "ip link set dev net34 down"
FAIL_LINK_CMD_UP = "ip link set dev net34 up"
CONVERGENCE_TIMEOUT = 60.0


def run_cmd(cmd: str, timeout: int = CMD_TIMEOUT) -> str:
    result = subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(output.strip() or f"Command failed: {cmd}")
    return output


def docker_exec(container: str, command: str, timeout: int = CMD_TIMEOUT) -> str:
    safe_command = command.replace('"', '\\"')
    return run_cmd(f'docker exec {container} sh -lc "{safe_command}"', timeout=timeout)


def flatten_metric_key(prefix: str, pair_name: str, suffix: str) -> str:
    clean = pair_name.lower().replace("-", "_")
    return f"{prefix}_{clean}_{suffix}"


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
    free_kb = meminfo.get("MemFree", 0)
    available_kb = meminfo.get("MemAvailable", free_kb)
    buffers_kb = meminfo.get("Buffers", 0)
    cached_kb = meminfo.get("Cached", 0)

    used_kb = max(total_kb - available_kb, 0)
    util_pct = (100.0 * used_kb / total_kb) if total_kb else 0.0

    return {
        "mem_total_mb": round(total_kb / 1024.0, 3),
        "mem_used_mb": round(used_kb / 1024.0, 3),
        "mem_free_mb": round(free_kb / 1024.0, 3),
        "mem_available_mb": round(available_kb / 1024.0, 3),
        "mem_buffers_mb": round(buffers_kb / 1024.0, 3),
        "mem_cached_mb": round(cached_kb / 1024.0, 3),
        "mem_utilisation_pct": round(util_pct, 3),
    }


def parse_ping_output(output: str) -> Optional[Dict[str, float]]:
    lines = output.splitlines()
    stats_line = next((l for l in lines if "min/avg/max" in l or "min/avg/max/mdev" in l), None)
    if not stats_line:
        return None

    stats_match = re.search(r'=\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)', stats_line)
    if not stats_match:
        raise RuntimeError(f"Could not parse ping summary line: {stats_line}")

    min_rtt, avg_rtt, max_rtt, stddev = map(float, stats_match.groups())

    samples = []
    for line in lines:
        match = re.search(r"time=([\d.]+)", line)
        if match:
            samples.append(float(match.group(1)))

    loss_match = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    txrx_match = re.search(r"(\d+)\s+packets transmitted,\s+(\d+)\s+received", output)

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
        "packet_loss_pct": packet_loss_pct,
        "packets_transmitted": packets_transmitted,
        "packets_received": packets_received,
        "sample_count": len(samples),
    }


def run_ping_metrics(src_container: str, dst_ip: str, count: int, interval: float, timeout: int = CMD_TIMEOUT) -> Dict[str, float]:
    output = docker_exec(src_container, f"ping -c {count} -i {interval} {dst_ip}", timeout=timeout)
    parsed = parse_ping_output(output)
    if not parsed:
        raise RuntimeError(f"Could not parse ping output for {src_container} -> {dst_ip}")
    return parsed


def run_iperf_metrics(src_container: str, dst_container: str, dst_ip: str, duration: int = IPERF_DURATION) -> Dict[str, float]:
    try:
        docker_exec(dst_container, "pkill -f iperf3 || true", timeout=15)
        docker_exec(src_container, "pkill -f iperf3 || true", timeout=15)
    except Exception:
        pass

    docker_exec(dst_container, "nohup iperf3 -s >/tmp/iperf3_server.log 2>&1 &", timeout=15)
    time.sleep(1.0)

    try:
        output = docker_exec(src_container, f"iperf3 -c {dst_ip} -t {duration} -J", timeout=duration + 30)
        data = json.loads(output)
        end = data.get("end", {})
        sent = end.get("sum_sent", {})
        received = end.get("sum_received", {})

        bandwidth_bps = float(sent.get("bits_per_second", 0.0))
        throughput_bps = float(received.get("bits_per_second", 0.0))
        retransmits = int(sent.get("retransmits", 0)) if sent.get("retransmits") is not None else 0

        return {
            "bandwidth_mbps": round(bandwidth_bps / 1_000_000.0, 6),
            "bandwidth_bps": round(bandwidth_bps, 3),
            "throughput_mbps": round(throughput_bps / 1_000_000.0, 6),
            "throughput_bps": round(throughput_bps, 3),
            "retransmits": retransmits,
        }
    finally:
        try:
            docker_exec(dst_container, "pkill -f iperf3 || true", timeout=15)
            docker_exec(src_container, "pkill -f iperf3 || true", timeout=15)
        except Exception:
            pass


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


def run_steady_state_benchmark(iterations: int = DEFAULT_ITERATIONS, pause_s: float = DEFAULT_PAUSE_BETWEEN_RUNS, output_file: str = DEFAULT_RESULTS_FILE) -> None:
    raw_runs = []
    csv_rows = []

    for i in range(1, iterations + 1):
        print(f"Steady-state iteration {i}/{iterations}")
        iteration_start = time.time()

        run_record = {
            "iteration": i,
            "started_at": datetime.datetime.now().isoformat(),
            "latency_jitter": {},
            "bandwidth_throughput": {},
            "packet_loss": {},
        }
        csv_row = {"iteration": i, "started_at": run_record["started_at"]}

        for pair in LATENCY_PAIRS:
            try:
                res = run_ping_metrics(pair["src_container"], pair["dst_ip"], count=PING_COUNT, interval=PING_INTERVAL)
                res["hops"] = pair["hops"]
                run_record["latency_jitter"][pair["name"]] = res
                csv_row[flatten_metric_key("latency", pair["name"], "hops")] = pair["hops"]
                for key in ("latency_min_ms", "latency_avg_ms", "latency_max_ms", "latency_std_ms", "latency_median_ms", "jitter_ms"):
                    csv_row[flatten_metric_key("latency", pair["name"], key)] = res.get(key)
            except Exception as e:
                run_record["latency_jitter"][pair["name"]] = {"error": str(e), "hops": pair["hops"]}
                csv_row[flatten_metric_key("latency", pair["name"], "error")] = str(e)

        for pair in BW_TPUT_PAIRS:
            try:
                res = run_iperf_metrics(pair["src_container"], pair["dst_container"], pair["dst_ip"], duration=IPERF_DURATION)
                res["hops"] = pair["hops"]
                run_record["bandwidth_throughput"][pair["name"]] = res
                csv_row[flatten_metric_key("bw", pair["name"], "hops")] = pair["hops"]
                for key in ("bandwidth_mbps", "bandwidth_bps", "throughput_mbps", "throughput_bps", "retransmits"):
                    csv_row[flatten_metric_key("bw", pair["name"], key)] = res.get(key)
            except Exception as e:
                run_record["bandwidth_throughput"][pair["name"]] = {"error": str(e), "hops": pair["hops"]}
                csv_row[flatten_metric_key("bw", pair["name"], "error")] = str(e)

        for pair in LOSS_PAIRS:
            try:
                res = run_ping_metrics(pair["src_container"], pair["dst_ip"], count=PACKET_LOSS_COUNT, interval=PING_INTERVAL)
                loss_record = {
                    "hops": pair["hops"],
                    "packet_loss_pct": res.get("packet_loss_pct"),
                    "packets_transmitted": res.get("packets_transmitted"),
                    "packets_received": res.get("packets_received"),
                }
                run_record["packet_loss"][pair["name"]] = loss_record
                csv_row[flatten_metric_key("loss", pair["name"], "hops")] = pair["hops"]
                for key in ("packet_loss_pct", "packets_transmitted", "packets_received"):
                    csv_row[flatten_metric_key("loss", pair["name"], key)] = loss_record.get(key)
            except Exception as e:
                run_record["packet_loss"][pair["name"]] = {"error": str(e), "hops": pair["hops"]}
                csv_row[flatten_metric_key("loss", pair["name"], "error")] = str(e)

        cpu_stats = measure_cpu_utilisation(duration_s=2.0)
        mem_stats = measure_memory_utilisation()
        duration_ms = round((time.time() - iteration_start) * 1000.0, 3)

        run_record["cpu_utilisation"] = cpu_stats
        run_record["memory_utilisation"] = mem_stats
        run_record["duration_ms"] = duration_ms

        csv_row.update(cpu_stats)
        csv_row.update(mem_stats)
        csv_row["duration_ms"] = duration_ms

        raw_runs.append(run_record)
        csv_rows.append(csv_row)

        if i < iterations and pause_s > 0:
            time.sleep(pause_s)

    summary = {
        "latency_jitter": {},
        "bandwidth_throughput": {},
        "packet_loss": {},
        "cpu_total_busy_pct": compute_numeric_summary([r["cpu_utilisation"].get("cpu_total_busy_pct") for r in raw_runs]),
        "mem_utilisation_pct": compute_numeric_summary([r["memory_utilisation"].get("mem_utilisation_pct") for r in raw_runs]),
        "duration_ms": compute_numeric_summary([r.get("duration_ms") for r in raw_runs]),
    }

    for pair in LATENCY_PAIRS:
        name = pair["name"]
        pair_runs = [r["latency_jitter"].get(name, {}) for r in raw_runs]
        summary["latency_jitter"][name] = {
            "hops": pair["hops"],
            "latency_min_ms": compute_numeric_summary([x.get("latency_min_ms") for x in pair_runs]),
            "latency_avg_ms": compute_numeric_summary([x.get("latency_avg_ms") for x in pair_runs]),
            "latency_max_ms": compute_numeric_summary([x.get("latency_max_ms") for x in pair_runs]),
            "latency_std_ms": compute_numeric_summary([x.get("latency_std_ms") for x in pair_runs]),
            "latency_median_ms": compute_numeric_summary([x.get("latency_median_ms") for x in pair_runs]),
            "jitter_ms": compute_numeric_summary([x.get("jitter_ms") for x in pair_runs]),
        }

    for pair in BW_TPUT_PAIRS:
        name = pair["name"]
        pair_runs = [r["bandwidth_throughput"].get(name, {}) for r in raw_runs]
        summary["bandwidth_throughput"][name] = {
            "hops": pair["hops"],
            "bandwidth_mbps": compute_numeric_summary([x.get("bandwidth_mbps") for x in pair_runs]),
            "throughput_mbps": compute_numeric_summary([x.get("throughput_mbps") for x in pair_runs]),
            "retransmits": compute_numeric_summary([x.get("retransmits") for x in pair_runs]),
        }

    for pair in LOSS_PAIRS:
        name = pair["name"]
        pair_runs = [r["packet_loss"].get(name, {}) for r in raw_runs]
        summary["packet_loss"][name] = {
            "hops": pair["hops"],
            "packet_loss_pct": compute_numeric_summary([x.get("packet_loss_pct") for x in pair_runs]),
        }

    json_payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "iterations_requested": iterations,
        "iterations_completed": len(raw_runs),
        "raw_runs": raw_runs,
        "summary": summary,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, indent=2)

    if csv_rows:
        csv_file = output_file.replace(".json", ".csv")
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)

    print(f"Steady-state JSON saved to {output_file}")
    print(f"Steady-state CSV saved to {output_file.replace('.json', '.csv')}")


def measure_convergence_once(container: str, dst_ip: str) -> Dict[str, Optional[float]]:
    docker_exec(container, FAIL_LINK_CMD_DOWN)
    start = time.time()

    failure_ms = None
    while (time.time() - start) <= CONVERGENCE_TIMEOUT:
        try:
            docker_exec(container, f"ping -c 1 -W 1 {dst_ip}", timeout=5)
            failure_ms = round((time.time() - start) * 1000.0, 3)
            break
        except Exception:
            pass

    docker_exec(container, FAIL_LINK_CMD_UP)
    start = time.time()

    recovery_ms = None
    while (time.time() - start) <= CONVERGENCE_TIMEOUT:
        try:
            docker_exec(container, f"ping -c 1 -W 1 {dst_ip}", timeout=5)
            recovery_ms = round((time.time() - start) * 1000.0, 3)
            break
        except Exception:
            pass

    return {"failure_ms": failure_ms, "recovery_ms": recovery_ms}


def run_convergence_tests(iterations: int = CONVERGENCE_ITERATIONS) -> None:
    rows = []
    for i in range(1, iterations + 1):
        print(f"Convergence iteration {i}/{iterations}")
        result = measure_convergence_once(CONVERGENCE_CONTAINER, CONVERGENCE_DST_IP)
        cpu_stats = measure_cpu_utilisation(duration_s=2.0)
        mem_stats = measure_memory_utilisation()

        row = {"iteration": i}
        row.update(result)
        row.update(cpu_stats)
        row.update(mem_stats)
        rows.append(row)

    if rows:
        with open(CONV_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        with open(CONV_JSON, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "iterations_requested": iterations,
                    "iterations_completed": len(rows),
                    "raw_runs": rows,
                    "summary": {
                        "failure_ms": compute_numeric_summary([r.get("failure_ms") for r in rows]),
                        "recovery_ms": compute_numeric_summary([r.get("recovery_ms") for r in rows]),
                        "cpu_total_busy_pct": compute_numeric_summary([r.get("cpu_total_busy_pct") for r in rows]),
                        "mem_utilisation_pct": compute_numeric_summary([r.get("mem_utilisation_pct") for r in rows]),
                    },
                },
                f,
                indent=2,
            )

    print(f"Convergence CSV saved to {CONV_CSV}")
    print(f"Convergence JSON saved to {CONV_JSON}")


def parse_args():
    parser = argparse.ArgumentParser(description="OSPF benchmark script")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS, help="Number of steady-state iterations")
    parser.add_argument("--convergence-iterations", type=int, default=CONVERGENCE_ITERATIONS, help="Number of convergence iterations")
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE_BETWEEN_RUNS, help="Pause between steady-state iterations in seconds")
    parser.add_argument("--output", default=DEFAULT_RESULTS_FILE, help="Steady-state JSON output filename")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_steady_state_benchmark(
        iterations=args.iterations,
        pause_s=args.pause,
        output_file=args.output,
    )
    run_convergence_tests(iterations=args.convergence_iterations)
