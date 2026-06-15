"""Generate a per-incident PDF report.

Usage:
    python reports/generate.py --id 1
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime

import httpx
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator import db  # noqa: E402
from orchestrator.config import settings  # noqa: E402

OUT_DIR = "reports/output"


def _fetch_alert(ip: str) -> dict:
    body = {
        "query": {"term": {"source_ip.keyword": ip}},
        "sort": [{"@timestamp": "desc"}],
        "size": 1,
    }
    try:
        r = httpx.post(f"{settings.es_url}/{settings.alerts_index}/_search", json=body, timeout=10.0)
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])
        if hits:
            return hits[0]["_source"]
    except Exception as e:
        print(f"warn: could not fetch alert from ES ({e}); rendering with minimal data")
    return {}


async def main(response_id: int) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    resp = await db.get(response_id)
    if not resp:
        print(f"No response with id={response_id}")
        sys.exit(1)

    a = _fetch_alert(resp["ip"])
    incident = {
        "id": resp["id"],
        "ip": resp["ip"],
        "attempt_count": a.get("attempt_count", "?"),
        "users": a.get("users", []),
        "first_seen": a.get("first_seen", "?"),
        "last_seen": a.get("last_seen", "?"),
        "rule_verdict": a.get("rule_verdict", "unknown"),
        "ml_verdict": a.get("ml_verdict", "unknown"),
        "ml_score": a.get("ml_score", 0.0),
        "final_verdict": a.get("final_verdict", "malicious"),
    }

    env = Environment(loader=FileSystemLoader("reports"))
    html = env.get_template("incident.html.j2").render(
        incident=incident,
        response=resp,
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    )

    from weasyprint import HTML  # imported lazy: heavy dependency
    out_path = os.path.join(OUT_DIR, f"incident_{response_id}.pdf")
    HTML(string=html).write_pdf(out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    args = ap.parse_args()
    asyncio.run(main(args.id))
