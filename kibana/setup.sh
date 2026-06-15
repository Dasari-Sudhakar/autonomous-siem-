#!/usr/bin/env bash
# Import the Kibana saved-objects (dashboards, index patterns) once ELK is up.
# Run after `make up` and after the first attack/baseline so the indices exist.
#
# Usage:  ./kibana/setup.sh

set -e
KBN="${KBN:-http://localhost:5601}"

echo "[*] Waiting for Kibana..."
until curl -fs "$KBN/api/status" >/dev/null 2>&1; do sleep 2; done

if [[ -f "$(dirname "$0")/dashboards.ndjson" ]]; then
    echo "[*] Importing saved objects from dashboards.ndjson"
    curl -X POST "$KBN/api/saved_objects/_import?overwrite=true" \
        -H "kbn-xsrf: true" \
        --form file=@"$(dirname "$0")/dashboards.ndjson"
    echo ""
    echo "[+] Done. Open $KBN/app/dashboards"
else
    echo "[!] dashboards.ndjson not present yet -- build dashboards in Kibana UI then export with:"
    echo "    curl -X POST '$KBN/api/saved_objects/_export' -H 'kbn-xsrf: true' \\"
    echo "         -H 'Content-Type: application/json' \\"
    echo "         -d '{\"type\":[\"dashboard\",\"visualization\",\"index-pattern\",\"search\"]}' \\"
    echo "         > kibana/dashboards.ndjson"
fi
