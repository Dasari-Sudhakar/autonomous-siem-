import asyncio
import logging
import time

from . import db, responder
from .config import settings
from .es_client import ESClient
from .ml_model import MLModel
from .rules import evaluate

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def run_once(es: ESClient, ml: MLModel) -> dict:
    events = await es.search_failed_ssh(settings.rule_window_seconds)
    if not events:
        return {"events": 0, "suspects": 0, "blocked": 0}

    suspects = evaluate(events)
    blocked = 0

    for ip, stats in suspects.items():
        ml_result = ml.score(stats)
        rule_malicious = stats["verdict"] == "malicious"
        ml_malicious = ml_result["verdict"] == "malicious"
        final = rule_malicious or ml_malicious

        await es.index_alert({
            "@timestamp": _now_iso(),
            "source_ip": ip,
            "attempt_count": stats["count"],
            "users": stats["users"],
            "first_seen": stats["first_seen"],
            "last_seen": stats["last_seen"],
            "rule_verdict": "malicious" if rule_malicious else "benign",
            "ml_verdict": ml_result["verdict"],
            "ml_score": ml_result["score"],
            "ml_trained": ml_result["trained"],
            "final_verdict": "malicious" if final else "benign",
        })

        if not (final and settings.enable_responder):
            continue
        if await db.is_blocked_recently(ip):
            log.info("%s already blocked recently — skipping", ip)
            continue

        killed = responder.kill_sessions_from(ip)
        if not responder.block_ip(ip):
            continue

        reason = f"rule={rule_malicious} ml={ml_malicious} count={stats['count']}"
        await db.record_block(ip, settings.block_ttl_seconds, reason, killed)
        await es.index_response({
            "@timestamp": _now_iso(),
            "ip": ip,
            "action": "block",
            "reason": reason,
            "sessions_killed": killed,
            "ttl_sec": settings.block_ttl_seconds,
        })
        blocked += 1
        log.warning("BLOCKED %s — %d attempts, %d sessions killed", ip, stats["count"], killed)

    return {"events": len(events), "suspects": len(suspects), "blocked": blocked}


async def cleanup_expired(es: ESClient) -> None:
    for entry in await db.get_expired_blocks():
        if responder.unblock_ip(entry["ip"]):
            await db.mark_rolled_back(entry["id"])
            await es.index_response({
                "@timestamp": _now_iso(),
                "ip": entry["ip"],
                "action": "unblock",
                "reason": "ttl_expired",
            })
            log.info("Rolled back block on %s", entry["ip"])


async def poll_loop() -> None:
    es = ESClient()
    ml = MLModel()
    await db.init()
    log.info(
        "Pipeline started. poll=%ds threshold=%d/%ds responder=%s dry_run=%s",
        settings.poll_interval_seconds,
        settings.rule_threshold,
        settings.rule_window_seconds,
        settings.enable_responder,
        settings.dry_run,
    )
    try:
        while True:
            try:
                result = await run_once(es, ml)
                if result["events"] or result["blocked"]:
                    log.info("poll: %s", result)
                await cleanup_expired(es)
            except Exception:
                log.exception("poll error")
            await asyncio.sleep(settings.poll_interval_seconds)
    finally:
        await es.close()
