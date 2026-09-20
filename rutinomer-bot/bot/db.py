"""SQLite-хранилище: пользователи, прохождения, лиды, платежи.

Лиды лежат тут же и выгружаются в CSV командой /leads - чтобы не терялись,
если Евгений пропустил уведомление в личке.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    full_name   TEXT,
    consent_at  TEXT,
    free_used   INTEGER NOT NULL DEFAULT 0,
    paid_credits INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    niche       TEXT,
    pain        TEXT,
    answers     TEXT,
    score       INTEGER,
    max_score   INTEGER,
    score10     INTEGER,
    paid        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    username    TEXT,
    offer_type  TEXT NOT NULL,
    contact     TEXT,
    niche       TEXT,
    score10     INTEGER,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    charge_id   TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    stars       INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    # --- пользователи -------------------------------------------------
    async def upsert_user(self, user_id: int, username: str, full_name: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """INSERT INTO users (user_id, username, full_name, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,
                                                     full_name=excluded.full_name""",
                (user_id, username, full_name, _now()),
            )
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def set_consent(self, user_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET consent_at = ? WHERE user_id = ? AND consent_at IS NULL",
                (_now(), user_id),
            )
            await db.commit()

    async def has_consent(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        return bool(user and user.get("consent_at"))

    # --- право на прохождение ----------------------------------------
    async def can_start(self, user_id: int) -> tuple[bool, bool]:
        """Возвращает (можно_начать, это_бесплатная_попытка)."""
        user = await self.get_user(user_id)
        if not user:
            return True, True
        if not user["free_used"]:
            return True, True
        return user["paid_credits"] > 0, False

    async def consume_attempt(self, user_id: int) -> bool:
        """Списывает попытку. True - была бесплатная, False - платная."""
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT free_used, paid_credits FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cur.fetchone()
            if row is None or not row["free_used"]:
                await db.execute(
                    "UPDATE users SET free_used = 1 WHERE user_id = ?", (user_id,)
                )
                await db.commit()
                return True
            await db.execute(
                "UPDATE users SET paid_credits = MAX(paid_credits - 1, 0) WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()
            return False

    async def add_paid_credit(self, user_id: int, charge_id: str, stars: int) -> bool:
        """Начисляет попытку за звезды. False - если платеж уже обработан."""
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT 1 FROM payments WHERE charge_id = ?", (charge_id,)
            )
            if await cur.fetchone():
                return False
            await db.execute(
                "INSERT INTO payments (charge_id, user_id, stars, created_at) VALUES (?, ?, ?, ?)",
                (charge_id, user_id, stars, _now()),
            )
            await db.execute(
                "UPDATE users SET paid_credits = paid_credits + 1 WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()
            return True

    # --- прохождения и лиды ------------------------------------------
    async def save_run(
        self,
        user_id: int,
        niche: str,
        pain: str,
        answers: list[dict[str, Any]],
        score: int,
        max_score: int,
        score10: int,
        paid: bool,
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """INSERT INTO runs (user_id, niche, pain, answers, score, max_score,
                                     score10, paid, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    niche,
                    pain,
                    json.dumps(answers, ensure_ascii=False),
                    score,
                    max_score,
                    score10,
                    int(paid),
                    _now(),
                ),
            )
            await db.commit()
            return int(cur.lastrowid or 0)

    async def save_lead(
        self,
        user_id: int,
        username: str,
        offer_type: str,
        contact: str,
        niche: str,
        score10: Optional[int],
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """INSERT INTO leads (user_id, username, offer_type, contact, niche,
                                      score10, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, username, offer_type, contact, niche, score10, _now()),
            )
            await db.commit()
            return int(cur.lastrowid or 0)

    async def all_leads(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM leads ORDER BY id DESC")
            return [dict(r) for r in await cur.fetchall()]

    async def forget_user(self, user_id: int) -> None:
        """Полное удаление по запросу пользователя. Платежи оставляем без
        привязки к личности - они нужны для сверки со Telegram."""
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM runs WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM leads WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            await db.commit()

    async def stats(self) -> dict[str, int]:
        async with aiosqlite.connect(self.path) as db:
            out: dict[str, int] = {}
            for key, sql in (
                ("users", "SELECT COUNT(*) FROM users"),
                ("consented", "SELECT COUNT(*) FROM users WHERE consent_at IS NOT NULL"),
                ("runs", "SELECT COUNT(*) FROM runs"),
                ("leads", "SELECT COUNT(*) FROM leads"),
                ("payments", "SELECT COUNT(*) FROM payments"),
                ("stars", "SELECT COALESCE(SUM(stars), 0) FROM payments"),
            ):
                cur = await db.execute(sql)
                row = await cur.fetchone()
                out[key] = int(row[0]) if row else 0
            return out
