#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# PART 2: configure_mininet_r1_frr.sh
#
# Purpose:
#   Configure Mininet R1 in FRR so that R1 advertises the SEED
#   network into the Mininet OSPF domain.
#
# Meaning:
#   Other Mininet routers learn:
#
#       To reach 10.0.0.0/16, go through R1.
#
# This is done by:
#   1. Adding a static route on R1 to the SEED network.
#   2. Redistributing static routes into OSPF on R1.
#
# Usage:
#   sudo ./configure_mininet_r1_frr.sh
# ============================================================

MININET_ROUTER_NAME="${MININET_ROUTER_NAME:-r1}"

SEED_NET="${SEED_NET:-10.0.0.0/16}"
SEED_BRIDGE_IP="${SEED_BRIDGE_IP:-172.16.100.1}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: Run with sudo."
    exit 1
fi

command -v mnexec >/dev/null 2>&1 || { echo "ERROR: mnexec not found."; exit 1; }

MININET_R1_PID="$(pgrep -f "mininet:${MININET_ROUTER_NAME}" | head -n 1 || true)"

if [[ -z "${MININET_R1_PID}" ]]; then
    echo "ERROR: Could not find Mininet namespace mininet:${MININET_ROUTER_NAME}"
    echo "Make sure Mininet is running."
    exit 1
fi

run_r1() {
    mnexec -a "${MININET_R1_PID}" "$@"
}

echo "Configuring FRR on Mininet ${MININET_ROUTER_NAME}..."
echo "R1 PID: ${MININET_R1_PID}"
echo

run_r1 vtysh -N "${MININET_ROUTER_NAME}" <<FRR_EOF
configure terminal
no ip route 10.0.0.0/8 ${SEED_BRIDGE_IP}
no ip route ${SEED_NET} ${SEED_BRIDGE_IP}
ip route ${SEED_NET} ${SEED_BRIDGE_IP}
router ospf
 redistribute static
end
write
FRR_EOF

echo
echo "Part 2 complete: R1 now advertises ${SEED_NET} into Mininet OSPF."
echo

echo "Verification 1: R1 FRR running config"
run_r1 vtysh -N "${MININET_ROUTER_NAME}" -c "show running-config" | grep -E "ip route|redistribute static|router ospf" || true

echo
echo "Verification 2: R1 route to SEED network"
run_r1 ip route get 10.0.200.254 || true

echo
echo "Verification 3: OSPF routes seen on R1"
run_r1 vtysh -N "${MININET_ROUTER_NAME}" -c "show ip route ospf" || true

echo
echo "To check other Mininet routers, run examples like:"
echo "  sudo mnexec -a \"\$(pgrep -f 'mininet:r2' | head -n 1)\" vtysh -N r2 -c 'show ip route'"
echo "  sudo mnexec -a \"\$(pgrep -f 'mininet:r2' | head -n 1)\" ping -c 4 10.0.200.254"