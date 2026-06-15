"""Train Isolation Forest on benign baseline ingested via Filebeat.

Usage:
    python ml/train.py --hours 1 --out ml/isolation_forest.pkl
"""
import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

import httpx
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator.config import settings  # noqa: E402


def fetch(hours: int) -> list[dict]:
    body = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"event.action": "ssh_login"}},
                    {"range": {"@timestamp": {"gte": f"now-{hours}h"}}},
                ]
            }
        },
        "size": 10000,
        "sort": [{"@timestamp": "asc"}],
    }
    r = httpx.post(f"{settings.es_url}/{settings.es_index}/_search", json=body, timeout=30.0)
    r.raise_for_status()
    return r.json()["hits"]["hits"]


def featurize(events: list[dict], window_sec: int = 60) -> np.ndarray:
    buckets: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for e in events:
        src = e.get("_source", {})
        ip = (src.get("source") or {}).get("ip")
        ts = src.get("@timestamp")
        if not (ip and ts):
            continue
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        bucket = int(when.timestamp()) // window_sec
        buckets[(ip, bucket)].append(src)

    rows = []
    for evs in buckets.values():
        count = len(evs)
        users = len({(e.get("user") or {}).get("name") for e in evs if (e.get("user") or {}).get("name")})
        t0 = datetime.fromisoformat(evs[0]["@timestamp"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(evs[-1]["@timestamp"].replace("Z", "+00:00"))
        span = max((t1 - t0).total_seconds(), 1.0)
        hour = t1.hour
        rows.append([count * 60.0 / span, float(users), float(hour), span])

    return np.array(rows) if rows else np.zeros((0, 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=1)
    ap.add_argument("--out", default="ml/isolation_forest.pkl")
    ap.add_argument("--contamination", type=float, default=0.05)
    args = ap.parse_args()

    print(f"Fetching last {args.hours}h of ssh_login events from {settings.es_url} ...")
    events = fetch(args.hours)
    print(f"Got {len(events)} events")

    X = featurize(events)
    print(f"Featurized into {X.shape[0]} per-IP per-minute windows")

    if X.shape[0] < 10:
        print("Not enough data. Generate baseline first:  ./attack/benign_traffic.sh 127.0.0.1 15")
        sys.exit(1)

    model = IsolationForest(contamination=args.contamination, random_state=42)
    model.fit(X)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    joblib.dump(model, args.out)
    print(f"Saved model to {args.out}")

    pred = model.predict(X)
    print(f"On training data: normal={(pred == 1).sum()}  anomalous={(pred == -1).sum()}")


if __name__ == "__main__":
    main()
