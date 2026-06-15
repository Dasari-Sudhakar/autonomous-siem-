from collections import defaultdict

from .config import settings


def evaluate(events: list[dict]) -> dict[str, dict]:
    """Group failed SSH events by source IP and produce per-IP stats."""
    by_ip: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        src = ev.get("_source", {})
        ip = (src.get("source") or {}).get("ip")
        if not ip:
            continue
        by_ip[ip].append(src)

    suspects: dict[str, dict] = {}
    for ip, ev_list in by_ip.items():
        count = len(ev_list)
        users = sorted({(e.get("user") or {}).get("name") for e in ev_list if (e.get("user") or {}).get("name")})
        timestamps = sorted([e["@timestamp"] for e in ev_list if "@timestamp" in e])
        suspects[ip] = {
            "ip": ip,
            "count": count,
            "users": users,
            "first_seen": timestamps[0] if timestamps else None,
            "last_seen": timestamps[-1] if timestamps else None,
            "verdict": "malicious" if count >= settings.rule_threshold else "suspicious",
        }
    return suspects
