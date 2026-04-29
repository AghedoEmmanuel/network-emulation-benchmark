#!/usr/bin/env python3

import subprocess
import csv
import re
from datetime import datetime

PING_COUNT = 500
PING_INTERVAL = 0.05
PING_TIMEOUT = 1

OUTPUT_CSV = "hybrid_latency_raw.csv"

MININET_ROUTERS = ["r1", "r2", "r3", "r4", "r5", "r6"]

SEED_TARGETS = {
    "seed_gateway": "10.0.200.253",
    "sr1": "10.0.12.254",
    "sr2": "10.0.12.253",
    "sr3": "10.0.23.253",
    "sr4": "10.0.34.253",
    "sr5": "10.0.45.253",
    "sr6": "10.0.56.253",
}

RTT_RE = re.compile(r"time=([\d.]+)\s*ms")


def get_router_pids():
    pids = {}

    for router in MININET_ROUTERS:
        cmd = f"pgrep -f 'mininet:{router}' | head -n 1"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        pid = result.stdout.strip()

        if not pid:
            raise RuntimeError(f"PID not found for {router}. Is Mininet running?")

        pids[router] = pid

    return pids


def run_ping(pid, target_ip):
    cmd = [
        "sudo", "mnexec", "-a", pid,
        "ping",
        "-c", str(PING_COUNT),
        "-i", str(PING_INTERVAL),
        "-W", str(PING_TIMEOUT),
        target_ip
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout + result.stderr

    return [float(x) for x in RTT_RE.findall(output)]


def main():
    rows = []

    print("\nStarting raw hybrid latency collection...\n")

    router_pids = get_router_pids()

    for router, pid in router_pids.items():
        for target_name, target_ip in SEED_TARGETS.items():
            print(f"Testing {router} -> {target_name} ({target_ip})")

            try:
                rtts = run_ping(pid, target_ip)

                for iteration, rtt in enumerate(rtts, start=1):
                    rows.append({
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "source_router": router,
                        "target_name": target_name,
                        "target_ip": target_ip,
                        "iteration": iteration,
                        "rtt_ms": rtt
                    })

            except Exception as e:
                print(f"ERROR: {router} -> {target_name}: {e}")

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp",
            "source_router",
            "target_name",
            "target_ip",
            "iteration",
            "rtt_ms"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print("\nDone.")
    print(f"Raw latency saved to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
