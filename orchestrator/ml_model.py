import os
from datetime import datetime

import joblib
import numpy as np

from .config import settings


def _features(stats: dict) -> list[float]:
    """[attempts_per_min, distinct_users, hour_of_day, span_seconds]"""
    count = stats["count"]
    users = len(stats["users"])
    try:
        t0 = datetime.fromisoformat(stats["first_seen"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(stats["last_seen"].replace("Z", "+00:00"))
        span = max((t1 - t0).total_seconds(), 1.0)
        hour = t1.hour
    except Exception:
        span = 60.0
        hour = 12
    attempts_per_min = count * 60.0 / span
    return [attempts_per_min, float(users), float(hour), span]


class MLModel:
    def __init__(self):
        self.model = None
        self.reload()

    def reload(self):
        if os.path.exists(settings.model_path):
            self.model = joblib.load(settings.model_path)

    def score(self, stats: dict) -> dict:
        if self.model is None:
            return {"trained": False, "score": 0.0, "verdict": "unknown"}
        X = np.array([_features(stats)])
        pred = int(self.model.predict(X)[0])  # 1 normal, -1 anomaly
        score = float(self.model.decision_function(X)[0])
        return {
            "trained": True,
            "score": score,
            "verdict": "malicious" if pred == -1 else "benign",
        }
