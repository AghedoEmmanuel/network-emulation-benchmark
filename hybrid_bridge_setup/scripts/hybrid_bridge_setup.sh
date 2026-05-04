#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# PART 1: setup_hybrid_link.sh
#
# Purpose:
#   Create the direct hybrid link between:
#
#       Mininet R1 <-> SEED gateway <-> SR1
#
#   This script creates the veth pair between Mininet R1 and the
#   SEED gateway, assigns the 172.16.100.0/30 bridge IPs, enables
#   forwarding, and adds immediate Linux routes between R1, the
#   SEED gateway, and SR1.
#
# This DOES NOT advertise routes through OSPF yet.
# OSPF advertisement is done in Part 2 and Part 3.
#
# Usage:
#   sudo ./setup_hybrid_link.sh <seed_gateway_container> <sr1_container>
#
# Example:
#   sudo ./setup_hybrid_link.sh 270e61e94928 1377af43db50
# ============================================================

MININET_ROUTER_NAME="${MININET_ROUTER_NAME:-r1}"

MININET_NET="${MININET_NET:-10.1.0.0/16}"
SEED_NET="${SEED_NET:-10.0.0.0/16}"
BRIDGE_NET="${BRIDGE_NET:-172.16.100.0/30}"

VETH_MININET="${VETH_MININET:-veth-mn}"
VETH_SEED="${VETH_SEED:-veth-seed}"
R1_EXT_IFACE="${R1_EXT_IFACE:-r1-ext}"

MININET_BRIDGE_IP_CIDR="${MININET_BRIDGE_IP_CIDR:-172.16.100.2/30}"
SEED_BRIDGE_IP_CIDR="${SEED_BRIDGE_IP_CIDR:-172.16.100.1/30}"

MININET_BRIDGE_IP="${MININET_BRIDGE_IP:-172.16.100.2}"
SEED_BRIDGE_IP="${SEED_BRIDGE_IP:-172.16.100.1}"

SEED_GATEWAY_INTERNAL_IP="${SEED_GATEWAY_INTERNAL_IP:-10.0.200.253}"
SR1_INTERNAL_IP="${SR1_INTERNAL_IP:-10.0.200.254}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: Run with sudo."
    exit 1
fi

if [[ "$#" -ne 2 ]]; then
    echo "Usage: sudo $0 <seed_gateway_container> <sr1_container>"
    exit 1
fi

SEED_GATEWAY_CONTAINER="$1"
SR1_CONTAINER="$2"

command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found."; exit 1; }
command -v mnexec >/dev/null 2>&1 || { echo "ERROR: mnexec not found."; exit 1; }
command -v ip >/dev/null 2>&1 || { echo "ERROR: ip command not found."; exit 1; }

MININET_R1_PID="$(pgrep -f "mininet:${MININET_ROUTER_NAME}" | head -n 1 || true)"

if [[ -z "${MININET_R1_PID}" ]]; then
    echo "ERROR: Could not find Mininet namespace mininet:${MININET_ROUTER_NAME}"
    echo "Make sure Mininet is already running."
    exit 1
fi

SEED_GATEWAY_PID="$(docker inspect -f '{{.State.Pid}}' "${SEED_GATEWAY_CONTAINER}")"
SR1_PID="$(docker inspect -f '{{.State.Pid}}' "${SR1_CONTAINER}")"

if [[ "${SEED_GATEWAY_PID}" == "0" || -z "${SEED_GATEWAY_PID}" ]]; then
    echo "ERROR: SEED gateway container is not running."
    exit 1
fi

if [[ "${SR1_PID}" == "0" || -z "${SR1_PID}" ]]; then
    echo "ERROR: SR1 container is not running."
    exit 1
fi

run_r1() {
    mnexec -a "${MININET_R1_PID}" "$@"
}

run_gateway() {
    docker exec "${SEED_GATEWAY_CONTAINER}" "$@"
}

run_sr1() {
    docker exec "${SR1_CONTAINER}" "$@"
}

echo "Detected:"
echo "  Mininet R1 PID: ${MININET_R1_PID}"
echo "  SEED gateway PID: ${SEED_GATEWAY_PID}"
echo "  SR1 PID: ${SR1_PID}"
echo

echo "Cleaning old hybrid link if it exists..."

ip link del "${VETH_MININET}" 2>/dev/null || true
ip link del "${VETH_SEED}" 2>/dev/null || true

run_r1 ip link del "${R1_EXT_IFACE}" 2>/dev/null || true
run_gateway ip link del "${VETH_SEED}" 2>/dev/null || true

run_r1 ip route del "${SEED_NET}" 2>/dev/null || true
run_r1 ip route del 10.0.0.0/8 2>/dev/null || true

run_gateway ip route del "${MININET_NET}" 2>/dev/null || true
run_gateway ip route del "${SEED_NET}" 2>/dev/null || true

run_sr1 ip route del "${MININET_NET}" 2>/dev/null || true
run_sr1 ip route del "${BRIDGE_NET}" 2>/dev/null || true

echo "Creating veth pair between Mininet R1 and SEED gateway..."

ip link add "${VETH_MININET}" type veth peer name "${VETH_SEED}"

ip link set "${VETH_MININET}" netns "${MININET_R1_PID}"
run_r1 ip link set "${VETH_MININET}" name "${R1_EXT_IFACE}"
run_r1 ip addr flush dev "${R1_EXT_IFACE}" || true
run_r1 ip addr add "${MININET_BRIDGE_IP_CIDR}" dev "${R1_EXT_IFACE}"
run_r1 ip link set "${R1_EXT_IFACE}" up

ip link set "${VETH_SEED}" netns "${SEED_GATEWAY_PID}"
run_gateway ip addr flush dev "${VETH_SEED}" || true
run_gateway ip addr add "${SEED_BRIDGE_IP_CIDR}" dev "${VETH_SEED}"
run_gateway ip link set "${VETH_SEED}" up

echo "Enabling IPv4 forwarding..."

run_r1 sysctl -w net.ipv4.ip_forward=1 >/dev/null
run_gateway sysctl -w net.ipv4.ip_forward=1 >/dev/null
run_sr1 sysctl -w net.ipv4.ip_forward=1 >/dev/null

echo "Adding immediate Linux routes..."

run_r1 ip route replace "${SEED_NET}" via "${SEED_BRIDGE_IP}" dev "${R1_EXT_IFACE}"
run_gateway ip route replace "${MININET_NET}" via "${MININET_BRIDGE_IP}" dev "${VETH_SEED}"
run_gateway ip route replace "${SEED_NET}" via "${SR1_INTERNAL_IP}"

run_sr1 ip route replace "${MININET_NET}" via "${SEED_GATEWAY_INTERNAL_IP}"
run_sr1 ip route replace "${BRIDGE_NET}" via "${SEED_GATEWAY_INTERNAL_IP}"

echo
echo "Part 1 complete: hybrid link configured."
echo

echo "Verification 1: Mininet R1 bridge interface"
run_r1 ip addr show "${R1_EXT_IFACE}"

echo
echo "Verification 2: SEED gateway bridge interface"
run_gateway ip addr show "${VETH_SEED}"

echo
echo "Verification 3: R1 pings SEED gateway"
run_r1 ping -c 4 "${SEED_BRIDGE_IP}"

echo
echo "Verification 4: SEED gateway pings R1"
run_gateway ping -c 4 "${MININET_BRIDGE_IP}"

echo
echo "Verification 5: R1 pings SR1"
run_r1 ping -c 4 "${SR1_INTERNAL_IP}" || true

echo
echo "Next:"
echo "  Run Part 2 to advertise the SEED route into Mininet OSPF."