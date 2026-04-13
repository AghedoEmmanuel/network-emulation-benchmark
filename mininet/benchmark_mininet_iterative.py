#!/usr/bin/env python3
"""
Dissertation Benchmark Script - SDN Side (Mininet/POX) - merged ms version
================================================================================
Operational definitions aligned as closely as practical with Golightly et al. (2023):
  - Latency        : ping RTT summary values stored in milliseconds
  - Jitter         : mean absolute deviation of ping RTT samples from average RTT, in milliseconds
  - Packet loss    : ping packet loss percentage
  - Bandwidth      : sender-side iperf3 TCP rate (operational proxy, Mbps / bps)
  - Throughput     : receiver-side iperf3 TCP rate (Mbps / bps)
  - SDN convergence: link-down/link-up recovery times in milliseconds
  - CPU utilisation: host system % via /proc/stat
  - Memory usage   : host system MB/% via /proc/meminfo
"""

import argparse
import csv
import datetime
import json
import re
import subprocess
import sys
import time
from statistics import mean, median, stdev

HOSTS = {
    "h1": "10.0.0.1",
    "h2": "10.0.0.2",
    "h4": "10.0.0.3",
    "h4": "10.0.0.4",
    "h5": "10.0.0.5",
    "h6": "10.0.0.6",
}

PING_COUNT = 100
PING_INTERVAL = 0.1
IPERF_DURATION = 10
PACKET_LOSS_COUNT = 200
DEFAULT_RESULTS_FILE = "sdn_benchmark_results_iterative_ms.json"
DEFAULT_ITERATIONS = 100
DEFAULT_CONVERGENCE_ITERATIONS = 30
DEFAULT_PAUSE_BETWEEN_RUNS = 2.0
CMD_TIMEOUT = 90

# Expanded to mirror expanded path route coverage more closely.
LATENCY_PAIRS = [
    ("h1", "h2"),
    ("h1", "h4"),
    ("h4", "h2"),
    ("h4", "h6"),
    ("h1", "h6"),
    ("h2", "h5"),
    ("h4", "h5"),
    ("h4", "h6"),
    ("h6", "h1"),
]
BW_TPUT_PAIRS = [("h1", "h2"), ("h1", "h4")]
LOSS_PAIRS = LATENCY_PAIRS[:]

# Shortest-path hop counts for the 6-node ring.
HOP_COUNTS = {
    "h1_to_h2": 1,
    "h1_to_h4": 2,
    "h4_to_h2": 1,
    "h4_to_h6": 2,
    "h1_to_h6": 1,
    "h2_to_h5": 2,
    "h4_to_h5": 1,
    "h4_to_h6": 2,
    "h6_to_h1": 1,
}

CONVERGENCE_SWITCH = "s1"
CONVERGENCE_INTERFACE = "s1-eth1"
CONVERGENCE_PING_SRC = "h1"
CONVERGENCE_PING_DST = HOSTS["h6"]
CONVERGENCE_POLL_SEC = 0.2
CONVERGENCE_TIMEOUT = 60


def pair_key(src, dst):
    return f"{src}_to_{dst}"


def section(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def run_shell(command, timeout=CMD_TIMEOUT):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        return (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def get_host_pid(host):
    output = run_shell(f"pgrep -f 'mininet:{host}' | head -1", timeout=10).strip()
    return output if output and output != "TIMEOUT" else None


def get_switch_pid(switch):
    output = run_shell(f"pgrep -f 'mininet:{switch}' | head -1", timeout=10).strip()
    return output if output and output != "TIMEOUT" else None


def run_mn_cmd(host, cmd, timeout=CMD_TIMEOUT):
    pid = get_host_pid(host)
    if not pid:
        return f"ERROR: Could not find Mininet PID for host {host}"
    return run_shell(f"mnexec -a {pid} {cmd}", timeout=timeout)


def run_switch_cmd(switch, cmd, timeout=CMD_TIMEOUT):
    pid = get_switch_pid(switch)
    if pid:
        return run_shell(f"mnexec -a {pid} {cmd}", timeout=timeout)
    return run_shell(cmd, timeout=timeout)


def validate_environment():
    issues = []
    for host in HOSTS:
        if not get_host_pid(host):
            issues.append(f"Host process not found for {host}")
    for binary in ("mnexec", "iperf3", "ping"):
        if not run_shell(f"command -v {binary}", timeout=10).strip():
            issues.append(f"Required command not found: {binary}")
    return issues


def _read_cpu_times():
    with open("/proc/stat", "r", encoding="utf-8") as f:
        line = f.readline()
    fields = line.split()
    labels = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal", "guest", "guest_nice"]
    times = {}
    for i, label in enumerate(labels):
        try:
            times[label] = int(fields[i + 1])
        except IndexError:
            times[label] = 0
    return times


def measure_cpu_utilisation(duration_s=1.0):
    try:
        t1 = _read_cpu_times()
        time.sleep(duration_s)
        t2 = _read_cpu_times()

        idle_delta = (t2["idle"] + t2["iowait"]) - (t1["idle"] + t1["iowait"])
        user_delta = (t2["user"] + t2["nice"]) - (t1["user"] + t1["nice"])
        sys_delta = t2["system"] - t1["system"]
        total_delta = sum(t2[k] - t1[k] for k in t1)
        if total_delta == 0:
            return {
                "user_pct": 0.0,
                "system_pct": 0.0,
                "total_busy_pct": 0.0,
                "sample_window_ms": round(duration_s * 1000.0, 3),
            }
        return {
            "user_pct": round(100.0 * user_delta / total_delta, 2),
            "system_pct": round(100.0 * sys_delta / total_delta, 2),
            "total_busy_pct": round(100.0 * (total_delta - idle_delta) / total_delta, 2),
            "sample_window_ms": round(duration_s * 1000.0, 3),
        }
    except Exception as e:
        return {"error": str(e)}


def measure_memory_utilisation():
    try:
        meminfo = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    meminfo[parts[0].rstrip(":")] = int(parts[1])

        total_mb = round(meminfo.get("MemTotal", 0) / 1024, 2)
        free_mb = round(meminfo.get("MemFree", 0) / 1024, 2)
        available_mb = round(meminfo.get("MemAvailable", 0) / 1024, 2)
        buffers_mb = round(meminfo.get("Buffers", 0) / 1024, 2)
        cached_mb = round(meminfo.get("Cached", 0) / 1024, 2)
        used_mb = round(total_mb - available_mb, 2)
        util_pct = round(100.0 * used_mb / total_mb, 2) if total_mb > 0 else 0.0
        return {
            "total_mb": total_mb,
            "used_mb": used_mb,
            "free_mb": free_mb,
            "available_mb": available_mb,
            "buffers_mb": buffers_mb,
            "cached_mb": cached_mb,
            "utilisation_pct": util_pct,
        }
    except Exception as e:
        return {"error": str(e)}


def parse_ping_samples_ms(output):
    return [float(x) for x in re.findall(r"time=([\d.]+)\s*ms", output)]


def parse_ping_summary_ms(output):
    rtt_match = re.search(r"rtt min/avg/max/(?:mdev|stddev) = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", output)
    loss_match = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    txrx_match = re.search(r"(\d+) packets transmitted, (\d+) received", output)

    values = {
        "latency_min_ms": None,
        "latency_avg_ms": None,
        "latency_max_ms": None,
        "latency_std_ms": None,
        "latency_median_ms": None,
        "packet_loss_pct": None,
        "packets_transmitted": None,
        "packets_received": None,
    }

    if rtt_match:
        mn, av, mx, sd = [float(v) for v in rtt_match.groups()]
        values.update({
            "latency_min_ms": mn,
            "latency_avg_ms": av,
            "latency_max_ms": mx,
            "latency_std_ms": sd,
        })

    if loss_match:
        values["packet_loss_pct"] = float(loss_match.group(1))

    if txrx_match:
        values["packets_transmitted"] = int(txrx_match.group(1))
        values["packets_received"] = int(txrx_match.group(2))

    return values


def compute_jitter(samples_ms):
    if not samples_ms:
        return None
    avg_ms = sum(samples_ms) / len(samples_ms)
    deviations = [abs(x - avg_ms) for x in samples_ms]
    return sum(deviations) / len(deviations)


def run_ping_metrics(src, dst, count=PING_COUNT, interval=PING_INTERVAL, timeout=CMD_TIMEOUT):
    dst_ip = HOSTS[dst]
    output = run_mn_cmd(src, f"ping -c {count} -i {interval} {dst_ip}", timeout=timeout)
    if output == "TIMEOUT":
        return {"error": "TIMEOUT"}

    summary = parse_ping_summary_ms(output)
    samples_ms = parse_ping_samples_ms(output)
    summary["latency_median_ms"] = round(median(samples_ms), 6) if samples_ms else None
    summary["jitter_ms"] = round(compute_jitter(samples_ms), 6) if samples_ms else None
    summary["sample_count"] = len(samples_ms)
    summary["hop_count"] = HOP_COUNTS.get(pair_key(src, dst))
    return summary


def test_latency_and_jitter(verbose=True):
    if verbose:
        section("LATENCY + JITTER TEST (ping, benchmark-aligned)")
    results = {}
    for src, dst in LATENCY_PAIRS:
        dst_ip = HOSTS[dst]
        hops = HOP_COUNTS.get(pair_key(src, dst), "?")
        if verbose:
            print(f"\n  {src} -> {dst} ({dst_ip}), hops={hops}, {PING_COUNT} packets...")
        metrics = run_ping_metrics(src, dst)
        if "error" not in metrics and metrics.get("latency_avg_ms") is not None:
            if verbose:
                print(
                    f"    hops={metrics['hop_count']}  min={metrics['latency_min_ms']:.6f}ms  avg={metrics['latency_avg_ms']:.6f}ms  "
                    f"max={metrics['latency_max_ms']:.6f}ms  std={metrics['latency_std_ms']:.6f}ms  "
                    f"median={metrics['latency_median_ms']:.6f}ms  jitter={metrics['jitter_ms']:.6f}ms  "
                    f"loss={metrics['packet_loss_pct']}%"
                )
        else:
            if verbose:
                print(f"    ERROR: {metrics}")
        results[pair_key(src, dst)] = metrics
    return results


def test_bandwidth_throughput(verbose=True):
    if verbose:
        section("BANDWIDTH + THROUGHPUT TEST (iperf3 TCP)")
    results = {}
    for src, dst in BW_TPUT_PAIRS:
        dst_ip = HOSTS[dst]
        if verbose:
            print(f"\n  {src} -> {dst} ({dst_ip}), {IPERF_DURATION}s TCP...")
        run_mn_cmd(dst, "pkill iperf3 2>/dev/null; sleep 0.5", timeout=15)
        server_pid = get_host_pid(dst)
        if not server_pid:
            results[pair_key(src, dst)] = {"error": f"No PID for {dst}"}
            continue

        subprocess.Popen(
            f"mnexec -a {server_pid} iperf3 -s -D",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)

        output = run_mn_cmd(src, f"iperf3 -c {dst_ip} -t {IPERF_DURATION} -J", timeout=IPERF_DURATION + 30)
        try:
            data = json.loads(output)
            sent = data["end"]["sum_sent"]
            recv = data["end"]["sum_received"]

            bandwidth_bps = float(sent["bits_per_second"])
            throughput_bps = float(recv["bits_per_second"])
            bandwidth_mbps = round(bandwidth_bps / 1e6, 3)
            throughput_mbps = round(throughput_bps / 1e6, 3)
            retransmits = sent.get("retransmits", 0)

            if verbose:
                print(
                    f"    bandwidth(sender)={bandwidth_mbps} Mbps  "
                    f"throughput(receiver)={throughput_mbps} Mbps  retransmits={retransmits}"
                )

            results[pair_key(src, dst)] = {
                "bandwidth_bps": bandwidth_bps,
                "bandwidth_mbps": bandwidth_mbps,
                "throughput_bps": throughput_bps,
                "throughput_mbps": throughput_mbps,
                "retransmits": retransmits,
                "duration_ms": round(IPERF_DURATION * 1000.0, 3),
            }
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if verbose:
                print(f"    ERROR: {exc}  raw: {output[:300]}")
            results[pair_key(src, dst)] = {"error": str(exc), "raw_output": output[:300]}
        finally:
            run_mn_cmd(dst, "pkill iperf3", timeout=15)
    return results


def test_packet_loss(verbose=True):
    if verbose:
        section("PACKET LOSS TEST")
    results = {}
    for src, dst in LOSS_PAIRS:
        dst_ip = HOSTS[dst]
        if verbose:
            print(f"\n  {src} -> {dst}, {PACKET_LOSS_COUNT} packets...")
        output = run_mn_cmd(src, f"ping -c {PACKET_LOSS_COUNT} -i 0.05 {dst_ip}")
        loss_match = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
        trans_match = re.search(r"(\d+) packets transmitted, (\d+) received", output)
        if loss_match and trans_match:
            loss = float(loss_match.group(1))
            tx, rx = int(trans_match.group(1)), int(trans_match.group(2))
            if verbose:
                print(f"    Transmitted: {tx}  Received: {rx}  Loss: {loss}%")
            results[pair_key(src, dst)] = {"transmitted": tx, "received": rx, "loss_pct": loss}
        else:
            if verbose:
                print(f"    ERROR: {output[:200]}")
            results[pair_key(src, dst)] = {"error": output[:300]}
    return results


def _ping_once_success(src_host, dst_ip):
    output = run_mn_cmd(src_host, f"ping -c 1 -W 1 {dst_ip}", timeout=5)
    return "1 received" in output or "0% packet loss" in output


def run_convergence_once(verbose=True):
    if verbose:
        print(f"  Checking baseline: {CONVERGENCE_PING_SRC} -> {CONVERGENCE_PING_DST} ...")

    if not _ping_once_success(CONVERGENCE_PING_SRC, CONVERGENCE_PING_DST):
        if verbose:
            print("  ERROR: Baseline ping failed — skipping this convergence run.")
        return {"failure_ms": None, "recovery_ms": None}

    if verbose:
        print(f"  Bringing {CONVERGENCE_INTERFACE} DOWN — starting failure timer ...")
    failure_start = time.time()
    run_switch_cmd(CONVERGENCE_SWITCH, f"ip link set dev {CONVERGENCE_INTERFACE} down", timeout=10)

    failure_ms = None
    deadline = failure_start + CONVERGENCE_TIMEOUT
    while time.time() < deadline:
        if _ping_once_success(CONVERGENCE_PING_SRC, CONVERGENCE_PING_DST):
            failure_ms = round((time.time() - failure_start) * 1000.0, 4)
            break
        time.sleep(CONVERGENCE_POLL_SEC)

    if verbose:
        if failure_ms is not None:
            print(f"  Failure convergence : {failure_ms:.4f} ms")
        else:
            print(f"  Failure convergence : TIMEOUT (>{CONVERGENCE_TIMEOUT} s)")

    time.sleep(1.0)

    if verbose:
        print(f"  Bringing {CONVERGENCE_INTERFACE} UP — starting recovery timer ...")
    recovery_start = time.time()
    run_switch_cmd(CONVERGENCE_SWITCH, f"ip link set dev {CONVERGENCE_INTERFACE} up", timeout=10)

    recovery_ms = None
    deadline = recovery_start + CONVERGENCE_TIMEOUT
    while time.time() < deadline:
        if _ping_once_success(CONVERGENCE_PING_SRC, CONVERGENCE_PING_DST):
            recovery_ms = round((time.time() - recovery_start) * 1000.0, 4)
            break
        time.sleep(CONVERGENCE_POLL_SEC)

    if verbose:
        if recovery_ms is not None:
            print(f"  Recovery convergence: {recovery_ms:.4f} ms")
        else:
            print(f"  Recovery convergence: TIMEOUT (>{CONVERGENCE_TIMEOUT} s)")

    time.sleep(2.0)
    return {"failure_ms": failure_ms, "recovery_ms": recovery_ms}


def run_convergence_phase(iterations, verbose=True):
    section(f"PHASE 2 — SDN CONVERGENCE ({iterations} iterations)")
    print(f"  Switch    : {CONVERGENCE_SWITCH}")
    print(f"  Interface : {CONVERGENCE_INTERFACE}")
    print(f"  Probe     : {CONVERGENCE_PING_SRC} -> {CONVERGENCE_PING_DST}\n")

    results = []
    for i in range(iterations):
        if verbose:
            print(f"  --- Convergence run {i + 1}/{iterations} ---")
        val = run_convergence_once(verbose=verbose)
        results.append(val)
        if verbose:
            print()

    failure_vals = [r["failure_ms"] for r in results if r["failure_ms"] is not None]
    recovery_vals = [r["recovery_ms"] for r in results if r["recovery_ms"] is not None]

    def summarise(vals):
        if not vals:
            return {"mean_ms": None, "min_ms": None, "max_ms": None, "stdev_ms": None, "successful_runs": 0}
        return {
            "mean_ms": round(mean(vals), 4),
            "min_ms": min(vals),
            "max_ms": max(vals),
            "stdev_ms": round(stdev(vals), 4) if len(vals) > 1 else 0.0,
            "successful_runs": len(vals),
        }

    summary = {
        "method": "link_down_up_poll",
        "interface_failed": CONVERGENCE_INTERFACE,
        "switch": CONVERGENCE_SWITCH,
        "probe_src": CONVERGENCE_PING_SRC,
        "probe_dst": CONVERGENCE_PING_DST,
        "iterations": iterations,
        "failure_convergence": summarise(failure_vals),
        "recovery_convergence": summarise(recovery_vals),
        "raw_results_ms": results,
    }

    section("CONVERGENCE SUMMARY")
    print(json.dumps({k: v for k, v in summary.items() if k != "raw_results_ms"}, indent=2))
    return summary


def extract_numeric_metric(runs, test_name, pair_name, metric_name):
    values = []
    for run in runs:
        val = run.get(test_name, {}).get(pair_name, {}).get(metric_name)
        if isinstance(val, (int, float)):
            values.append(float(val))
    return values


def compute_summary(runs):
    summary = {
        "latency": {},
        "latency_median": {},
        "jitter": {},
        "bandwidth": {},
        "throughput": {},
        "packet_loss": {},
        "cpu_utilisation": {},
        "memory_utilisation": {},
    }

    def stats(vals):
        if not vals:
            return {}
        return {
            "mean": round(mean(vals), 6),
            "stdev": round(stdev(vals), 6) if len(vals) > 1 else 0.0,
            "min": min(vals),
            "max": max(vals),
            "samples": len(vals),
        }

    for src, dst in LATENCY_PAIRS:
        pair = pair_key(src, dst)
        lat_vals = extract_numeric_metric(runs, "latency_jitter", pair, "latency_avg_ms")
        median_vals = extract_numeric_metric(runs, "latency_jitter", pair, "latency_median_ms")
        jit_vals = extract_numeric_metric(runs, "latency_jitter", pair, "jitter_ms")
        if lat_vals:
            summary["latency"][pair] = {**stats(lat_vals), "hop_count": HOP_COUNTS.get(pair)}
        if median_vals:
            summary["latency_median"][pair] = {**stats(median_vals), "hop_count": HOP_COUNTS.get(pair)}
        if jit_vals:
            summary["jitter"][pair] = {**stats(jit_vals), "hop_count": HOP_COUNTS.get(pair)}

    for src, dst in BW_TPUT_PAIRS:
        pair = pair_key(src, dst)
        bw_vals = extract_numeric_metric(runs, "bandwidth_throughput", pair, "bandwidth_mbps")
        tp_vals = extract_numeric_metric(runs, "bandwidth_throughput", pair, "throughput_mbps")
        if bw_vals:
            summary["bandwidth"][pair] = stats(bw_vals)
        if tp_vals:
            summary["throughput"][pair] = stats(tp_vals)

    for src, dst in LOSS_PAIRS:
        pair = pair_key(src, dst)
        vals = extract_numeric_metric(runs, "packet_loss", pair, "loss_pct")
        if vals:
            summary["packet_loss"][pair] = {**stats(vals), "hop_count": HOP_COUNTS.get(pair)}

    cpu_vals = [
        r.get("cpu_utilisation", {}).get("total_busy_pct")
        for r in runs
        if isinstance(r.get("cpu_utilisation", {}).get("total_busy_pct"), (int, float))
    ]
    if cpu_vals:
        summary["cpu_utilisation"] = stats(cpu_vals)

    mem_vals = [
        r.get("memory_utilisation", {}).get("utilisation_pct")
        for r in runs
        if isinstance(r.get("memory_utilisation", {}).get("utilisation_pct"), (int, float))
    ]
    if mem_vals:
        summary["memory_utilisation"] = stats(mem_vals)

    return summary


def _build_csv_fieldnames():
    fieldnames = ["iteration", "started_at", "completed_at", "duration_ms"]

    for src, dst in LATENCY_PAIRS:
        base = f"latency_{src}_{dst}"
        fieldnames.extend([
            f"{base}_hops",
            f"{base}_min_ms",
            f"{base}_avg_ms",
            f"{base}_max_ms",
            f"{base}_std_ms",
            f"{base}_median_ms",
            f"jitter_{src}_{dst}_ms",
            f"{base}_loss_pct",
        ])

    for src, dst in BW_TPUT_PAIRS:
        fieldnames.extend([
            f"bandwidth_{src}_{dst}_mbps",
            f"throughput_{src}_{dst}_mbps",
            f"retransmits_{src}_{dst}",
        ])

    for src, dst in LOSS_PAIRS:
        fieldnames.append(f"packetloss_{src}_{dst}_pct")

    fieldnames.extend([
        "cpu_total_busy_pct",
        "cpu_user_pct",
        "cpu_system_pct",
        "cpu_sample_window_ms",
        "mem_used_mb",
        "mem_total_mb",
        "mem_utilisation_pct",
    ])
    return fieldnames


def save_csv(all_runs, csv_file):
    fieldnames = _build_csv_fieldnames()

    def g(d, *keys):
        for k in keys:
            if not isinstance(d, dict):
                return ""
            d = d.get(k, "")
        return "" if d == "" or d is None else d

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for run in all_runs:
            lj = run.get("latency_jitter", {})
            bt = run.get("bandwidth_throughput", {})
            loss = run.get("packet_loss", {})
            cpu = run.get("cpu_utilisation", {})
            mem = run.get("memory_utilisation", {})
            row = {
                "iteration": run.get("iteration", ""),
                "started_at": run.get("started_at", ""),
                "completed_at": run.get("completed_at", ""),
                "duration_ms": run.get("duration_ms", ""),
                "cpu_total_busy_pct": cpu.get("total_busy_pct", ""),
                "cpu_user_pct": cpu.get("user_pct", ""),
                "cpu_system_pct": cpu.get("system_pct", ""),
                "cpu_sample_window_ms": cpu.get("sample_window_ms", ""),
                "mem_used_mb": mem.get("used_mb", ""),
                "mem_total_mb": mem.get("total_mb", ""),
                "mem_utilisation_pct": mem.get("utilisation_pct", ""),
            }

            for src, dst in LATENCY_PAIRS:
                pair = pair_key(src, dst)
                base = f"latency_{src}_{dst}"
                row.update({
                    f"{base}_hops": g(lj, pair, "hop_count"),
                    f"{base}_min_ms": g(lj, pair, "latency_min_ms"),
                    f"{base}_avg_ms": g(lj, pair, "latency_avg_ms"),
                    f"{base}_max_ms": g(lj, pair, "latency_max_ms"),
                    f"{base}_std_ms": g(lj, pair, "latency_std_ms"),
                    f"{base}_median_ms": g(lj, pair, "latency_median_ms"),
                    f"jitter_{src}_{dst}_ms": g(lj, pair, "jitter_ms"),
                    f"{base}_loss_pct": g(lj, pair, "packet_loss_pct"),
                })

            for src, dst in BW_TPUT_PAIRS:
                pair = pair_key(src, dst)
                row.update({
                    f"bandwidth_{src}_{dst}_mbps": g(bt, pair, "bandwidth_mbps"),
                    f"throughput_{src}_{dst}_mbps": g(bt, pair, "throughput_mbps"),
                    f"retransmits_{src}_{dst}": g(bt, pair, "retransmits"),
                })

            for src, dst in LOSS_PAIRS:
                pair = pair_key(src, dst)
                row[f"packetloss_{src}_{dst}_pct"] = g(loss, pair, "loss_pct")

            writer.writerow(row)
    print(f"CSV saved to {csv_file}")


def save_convergence_results(convergence_summary, output_file):
    if not convergence_summary:
        print("No convergence results to save.")
        return

    conv_json_file = output_file.replace(".json", "_convergence.json")
    conv_csv_file = output_file.replace(".json", "_convergence.csv")

    with open(conv_json_file, "w", encoding="utf-8") as f:
        json.dump(convergence_summary, f, indent=2)
    print(f"\nConvergence JSON saved to {conv_json_file}")

    raw_runs = convergence_summary.get("raw_results_ms", [])
    with open(conv_csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["iteration", "failure_ms", "recovery_ms"])
        writer.writeheader()
        for i, run in enumerate(raw_runs, start=1):
            writer.writerow({
                "iteration": i,
                "failure_ms": run.get("failure_ms", ""),
                "recovery_ms": run.get("recovery_ms", ""),
            })
    print(f"Convergence CSV saved to {conv_csv_file}")


def save_results(all_runs, output_file, iterations_requested):
    payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "environment": "SDN - Mininet + POX Controller",
        "topology": "6-node ring, 6 hosts, OpenFlow 1.0",
        "iterations_requested": iterations_requested,
        "iterations_completed": len(all_runs),
        "hop_counts": HOP_COUNTS,
        "metric_definition": {
            "latency": "ping RTT summary in milliseconds",
            "jitter": "mean absolute deviation of ping RTT samples from average RTT, in milliseconds",
            "latency_median": "median of individual ping RTT samples in milliseconds",
            "bandwidth": "iperf3 sender-side achieved TCP rate",
            "throughput": "iperf3 receiver-side achieved TCP rate",
            "convergence": "link-down/link-up recovery time in milliseconds",
        },
        "runs": all_runs,
        "summary": compute_summary(all_runs),
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nResults saved to {output_file}")
    save_csv(all_runs, output_file.replace(".json", ".csv"))


def parse_args():
    parser = argparse.ArgumentParser(description="Iterative Mininet/POX benchmark runner (benchmark-aligned)")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--convergence-iterations", type=int, default=DEFAULT_CONVERGENCE_ITERATIONS)
    parser.add_argument("--skip-convergence", action="store_true")
    parser.add_argument("--output", default=DEFAULT_RESULTS_FILE)
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE_BETWEEN_RUNS)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    verbose = not args.quiet

    section("DISSERTATION BENCHMARK - ITERATIVE SDN SIDE (BENCHMARK-ALIGNED)")
    print(f"Steady-state iterations  : {args.iterations}")
    print(f"Convergence iterations   : {0 if args.skip_convergence else args.convergence_iterations}")
    print(f"Output file              : {args.output}")
    print(f"Pause between runs       : {args.pause} seconds")

    issues = validate_environment()
    if issues:
        print("\nEnvironment validation failed:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)

    section("PHASE 1 — STEADY-STATE PERFORMANCE")
    all_runs = []

    try:
        for i in range(args.iterations):
            section(f"ITERATION {i + 1}/{args.iterations}")
            iteration_result = {"iteration": i + 1, "started_at": datetime.datetime.now().isoformat()}
            run_start = time.time()

            iteration_result["latency_jitter"] = test_latency_and_jitter(verbose=verbose)
            iteration_result["bandwidth_throughput"] = test_bandwidth_throughput(verbose=verbose)
            iteration_result["packet_loss"] = test_packet_loss(verbose=verbose)
            iteration_result["cpu_utilisation"] = measure_cpu_utilisation(duration_s=2.0)
            iteration_result["memory_utilisation"] = measure_memory_utilisation()
            iteration_result["duration_ms"] = round((time.time() - run_start) * 1000.0, 3)
            iteration_result["completed_at"] = datetime.datetime.now().isoformat()
            all_runs.append(iteration_result)

            print(f"\nIteration {i + 1} completed in {iteration_result['duration_ms']} ms")
            if i < args.iterations - 1 and args.pause > 0:
                time.sleep(args.pause)
    except KeyboardInterrupt:
        print("\nBenchmark interrupted. Saving completed runs...")

    convergence_summary = None
    if not args.skip_convergence:
        convergence_summary = run_convergence_phase(args.convergence_iterations, verbose=verbose)

    save_results(all_runs, args.output, args.iterations)
    if convergence_summary:
        save_convergence_results(convergence_summary, args.output)

    section("FINAL SUMMARY — STEADY-STATE")
    print(f"Completed: {len(all_runs)}/{args.iterations} iterations")
    print(json.dumps(compute_summary(all_runs), indent=2))


if __name__ == "__main__":
    main()
