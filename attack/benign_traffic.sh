#!/usr/bin/env bash
# Generate slow, mostly-successful SSH activity so Isolation Forest has a baseline.
# Run on the SIEM host (the Ubuntu box) for ~15+ minutes BEFORE training.
#
# Usage:  ./attack/benign_traffic.sh [target-ip] [duration-minutes]

set -e

TARGET="${1:-127.0.0.1}"
DURATION_MIN="${2:-15}"
WHO="${USER:-$(whoami)}"

echo "[*] Generating benign baseline against $TARGET as user '$WHO' for $DURATION_MIN minutes."
END=$(( $(date +%s) + DURATION_MIN*60 ))

# We won't actually be able to log in (no password / no key), but the connection
# generates "Failed password" / "Connection closed" auth.log entries with a low,
# irregular rate -- exactly what we want for the benign baseline.
while [ "$(date +%s)" -lt "$END" ]; do
    ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=3 \
        "$WHO@$TARGET" 'exit' >/dev/null 2>&1 || true

    # Occasional typo username
    if (( RANDOM % 10 == 0 )); then
        ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=3 \
            "wrongname@$TARGET" 'exit' >/dev/null 2>&1 || true
    fi

    sleep $(( 20 + RANDOM % 30 ))
done

echo "[*] Baseline generation complete."
