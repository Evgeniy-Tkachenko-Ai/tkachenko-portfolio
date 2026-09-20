"""Служебные команды для Евгения: статистика и выгрузка лидов."""
from __future__ import annotations

import csv
import io

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from ..config import Config
from ..db import Database

router = Router(name="admin")

LEAD_COLUMNS = [
    "id",
    "created_at",
    "user_id",
    "username",
    "offer_type",
    "score10",
    "niche",
    "contact",
]


def _is_admin(message: Message, config: Config) -> bool:
    return bool(config.admin_chat_id) and message.chat.id == config.admin_chat_id


@router.message(Command("stats"))
async def stats(message: Message, db: Database, config: Config) -> None:
    if not _is_admin(message, config):
        return
    s = await db.stats()
    await message.answer(
        "Статистика\n\n"
        f"Пользователей: {s['users']}\n"
        f"Дали согласие: {s['consented']}\n"
        f"Прохождений: {s['runs']}\n"
        f"Лидов: {s['leads']}\n"
        f"Оплат: {s['payments']} (всего {s['stars']} звезд)"
    )


@router.message(Command("leads"))
async def leads(message: Message, db: Database, config: Config) -> None:
    if not _is_admin(message, config):
        return
    rows = await db.all_leads()
    if not rows:
        await message.answer("Лидов пока нет.")
        return
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=LEAD_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    await message.answer_document(
        BufferedInputFile(
            buffer.getvalue().encode("utf-8-sig"), filename="leads.csv"
        ),
        caption=f"Лидов: {len(rows)}",
    )
