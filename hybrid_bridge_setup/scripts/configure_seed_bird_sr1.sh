#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# PART 3: configure_sr1_bird_manual.sh
#
# Purpose:
#   Open /etc/bird/bird.conf inside the SR1 container so the user
#   can manually edit the BIRD configuration. After the editor is
#   closed, the script reloads BIRD and checks whether the Mininet
#   route is visible.
#
# Why this version exists:
#   BIRD configuration files can differ between SEED builds. Fully
#   automatic editing can be risky, especially when protocol pipe,
#   import/export rules, or multiple routing tables are involved.
#   This script keeps the edit manual but automates the safe steps:
#
#   1. Back up /etc/bird/bird.conf
#   2. Show the route snippet that should be added
#   3. Open /etc/bird/bird.conf inside SR1
#   4. Reload BIRD after the file is closed
#   5. Check whether the Mininet route appears
#
# Usage:
#   sudo ./scripts/part3_configure_sr1_bird_manual.sh <sr1_container>
#
# Example:
#   sudo ./scripts/part3_configure_sr1_bird_manual.sh 1377af43db50
#
# Optional:
#   sudo ./scripts/part3_configure_sr1_bird_manual.sh <sr1_container> <snippet_file>
#
# Example:
#   sudo ./scripts/part3_configure_sr1_bird_manual.sh 1377af43db50 configs/sr1_bird_mininet_static.conf
# ============================================================

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: Run this script with sudo."
    exit 1
fi

if [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
    echo "Usage: sudo $0 <sr1_container> [snippet_file]"
    exit 1
fi

SR1_CONTAINER="$1"
SNIPPET_FILE="${2:-configs/sr1_bird_mininet_static.conf}"

MININET_NET="${MININET_NET:-10.1.0.0/16}"
MININET_GREP="${MININET_GREP:-10.1}"
BIRD_CONF="/etc/bird/bird.conf"
BACKUP_CONF="/etc/bird/bird.conf.bak"

command -v docker >/dev/null 2>&1 || {
    echo "ERROR: docker not found."
    exit 1
}

docker exec "${SR1_CONTAINER}" test -f "${BIRD_CONF}" || {
    echo "ERROR: ${BIRD_CONF} not found inside ${SR1_CONTAINER}."
    exit 1
}

echo "Using SR1 container: ${SR1_CONTAINER}"
echo "Target BIRD file: ${BIRD_CONF}"
echo

echo "Backing up ${BIRD_CONF} to ${BACKUP_CONF}..."
docker exec "${SR1_CONTAINER}" cp "${BIRD_CONF}" "${BACKUP_CONF}"

echo
echo "Current BIRD protocols:"
docker exec "${SR1_CONTAINER}" birdc show protocols || true

echo
echo "Suggested BIRD static route snippet:"
echo "------------------------------------------------------------"

if [[ -f "${SNIPPET_FILE}" ]]; then
    cat "${SNIPPET_FILE}"
    echo "------------------------------------------------------------"
    echo
    echo "Copying snippet into SR1 as /tmp/sr1_bird_mininet_static.conf for reference..."
    docker cp "${SNIPPET_FILE}" "${SR1_CONTAINER}:/tmp/sr1_bird_mininet_static.conf"
else
    cat <<'SNIPPET'
protocol static mininet_static {
    ipv4;

    route 10.1.0.0/16 via 10.0.200.253;
    route 172.16.100.0/30 via 10.0.200.253;
}
SNIPPET
    echo "------------------------------------------------------------"
    echo
    echo "WARNING: Snippet file was not found at: ${SNIPPET_FILE}"
    echo "The default snippet above is shown for manual copying."
fi

cat <<'INSTRUCTIONS'

Manual changes to make inside /etc/bird/bird.conf:

1. Add the mininet_static block before the protocol ospf section:

   protocol static mininet_static {
       ipv4;

       route 10.1.0.0/16 via 10.0.200.253;
       route 172.16.100.0/30 via 10.0.200.253;
   }

2. Inside the relevant protocol ospf ipv4 block, use:

   ipv4 {
       import all;
       export where source = RTS_STATIC;
   };

3. If there is a relevant protocol pipe block and it currently has:

   import none;

   change only the relevant pipe to:

   import all;

Do not blindly change every import/export line in the file.
Only change the OSPF/pipe section that controls the SEED routing table used by SR1.

When you save and close the editor, this script will run:
   birdc configure
   birdc show route | grep 10.1

INSTRUCTIONS

read -r -p "Press Enter to open /etc/bird/bird.conf inside SR1..."

EDITOR_CMD="$(docker exec "${SR1_CONTAINER}" sh -lc 'command -v nano || command -v vim || command -v vi || true')"

if [[ -z "${EDITOR_CMD}" ]]; then
    echo
    echo "ERROR: No editor found inside ${SR1_CONTAINER}."
    echo "Install nano/vi in the container or edit manually with:"
    echo "  sudo docker exec -it ${SR1_CONTAINER} bash"
    echo "  cat ${BIRD_CONF}"
    exit 1
fi

echo "Opening ${BIRD_CONF} using ${EDITOR_CMD}..."
docker exec -it "${SR1_CONTAINER}" "${EDITOR_CMD}" "${BIRD_CONF}"

echo
echo "Editor closed."
echo "Checking BIRD configuration syntax by reloading BIRD..."
echo

if docker exec "${SR1_CONTAINER}" birdc configure; then
    echo
    echo "BIRD reloaded successfully."
else
    echo
    echo "ERROR: BIRD reload failed. The previous running BIRD config is likely still active,"
    echo "but the file on disk contains a syntax/configuration problem."
    echo
    read -r -p "Restore backup file now? [y/N]: " RESTORE_ANSWER

    case "${RESTORE_ANSWER}" in
        y|Y|yes|YES)
            echo "Restoring ${BACKUP_CONF} to ${BIRD_CONF}..."
            docker exec "${SR1_CONTAINER}" cp "${BACKUP_CONF}" "${BIRD_CONF}"
            docker exec "${SR1_CONTAINER}" birdc configure || true
            echo "Backup restored."
            ;;
        *)
            echo "Backup not restored. You can restore it manually with:"
            echo "  sudo docker exec ${SR1_CONTAINER} cp ${BACKUP_CONF} ${BIRD_CONF}"
            echo "  sudo docker exec ${SR1_CONTAINER} birdc configure"
            ;;
    esac

    exit 1
fi

echo
echo "Checking whether SR1 has the Mininet route (${MININET_NET})..."
docker exec "${SR1_CONTAINER}" birdc show route | grep "${MININET_GREP}" || {
    echo "WARNING: No route containing ${MININET_GREP} was found in SR1's BIRD route table."
    echo "Check the static block and OSPF export/pipe settings."
}

echo
echo "Checking exported routes containing ${MININET_GREP}..."
docker exec "${SR1_CONTAINER}" birdc show route export all | grep "${MININET_GREP}" || true

echo
echo "Part 3 manual BIRD configuration complete."
echo
echo "Now check another SEED router, for example:"
echo "  sudo docker exec -it <another_seed_router> birdc show route | grep ${MININET_GREP}"