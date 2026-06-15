import time

import aiosqlite

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ip              TEXT    NOT NULL,
    blocked_at      INTEGER NOT NULL,
    ttl_sec         INTEGER NOT NULL,
    rolled_back_at  INTEGER,
    reason          TEXT,
    sessions_killed INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_responses_ip     ON responses(ip);
CREATE INDEX IF NOT EXISTS idx_responses_active ON responses(rolled_back_at);
"""


async def init() -> None:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


async def is_blocked_recently(ip: str, window_sec: int = 3600) -> bool:
    cutoff = int(time.time()) - window_sec
    async with aiosqlite.connect(settings.sqlite_path) as db:
        async with db.execute(
            "SELECT 1 FROM responses WHERE ip = ? AND blocked_at > ? AND rolled_back_at IS NULL LIMIT 1",
            (ip, cutoff),
        ) as cur:
            return (await cur.fetchone()) is not None


async def record_block(ip: str, ttl_sec: int, reason: str, sessions_killed: int) -> int:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        cur = await db.execute(
            "INSERT INTO responses (ip, blocked_at, ttl_sec, reason, sessions_killed) VALUES (?, ?, ?, ?, ?)",
            (ip, int(time.time()), ttl_sec, reason, sessions_killed),
        )
        await db.commit()
        return cur.lastrowid


async def get_expired_blocks() -> list[dict]:
    now = int(time.time())
    async with aiosqlite.connect(settings.sqlite_path) as db:
        async with db.execute(
            "SELECT id, ip FROM responses WHERE rolled_back_at IS NULL AND blocked_at + ttl_sec < ?",
            (now,),
        ) as cur:
            return [{"id": r[0], "ip": r[1]} for r in await cur.fetchall()]


async def mark_rolled_back(response_id: int) -> None:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute(
            "UPDATE responses SET rolled_back_at = ? WHERE id = ?",
            (int(time.time()), response_id),
        )
        await db.commit()


async def list_active() -> list[dict]:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        async with db.execute(
            "SELECT id, ip, blocked_at, ttl_sec, reason, sessions_killed "
            "FROM responses WHERE rolled_back_at IS NULL ORDER BY blocked_at DESC"
        ) as cur:
            return [
                {"id": r[0], "ip": r[1], "blocked_at": r[2], "ttl_sec": r[3], "reason": r[4], "sessions_killed": r[5]}
                for r in await cur.fetchall()
            ]


async def get(response_id: int) -> dict | None:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        async with db.execute(
            "SELECT id, ip, blocked_at, ttl_sec, reason, sessions_killed, rolled_back_at "
            "FROM responses WHERE id = ?",
            (response_id,),
        ) as cur:
            r = await cur.fetchone()
            if not r:
                return None
            return {
                "id": r[0], "ip": r[1], "blocked_at": r[2], "ttl_sec": r[3],
                "reason": r[4], "sessions_killed": r[5], "rolled_back_at": r[6],
            }
