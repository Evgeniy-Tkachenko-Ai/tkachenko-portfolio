"""Конфиг. Все секреты - только из окружения, в коде их нет и быть не может."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Не задана переменная окружения {name}. "
            "Скопируй .env.example в .env и заполни."
        )
    return value


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    bot_token: str
    anthropic_api_key: str
    admin_chat_id: int
    model: str
    price_stars: int
    db_path: str
    site_url: str
    chat_url: str
    port: int
    keepalive_url: str
    keepalive_interval: int

    @classmethod
    def load(cls) -> "Config":
        return cls(
            bot_token=_req("BOT_TOKEN"),
            anthropic_api_key=_req("ANTHROPIC_API_KEY"),
            admin_chat_id=_int("ADMIN_CHAT_ID", 0),
            model=os.getenv("CLAUDE_MODEL", "claude-opus-5").strip() or "claude-opus-5",
            price_stars=_int("PRICE_STARS", 188),
            db_path=os.getenv("DB_PATH", "data/bot.db").strip() or "data/bot.db",
            site_url=os.getenv("SITE_URL", "https://tkachenko-ai.com").strip(),
            chat_url=os.getenv("CHAT_URL", "").strip(),
            port=_int("PORT", 8080),
            keepalive_url=os.getenv("KEEPALIVE_URL", "").strip().rstrip("/"),
            keepalive_interval=_int("KEEPALIVE_INTERVAL", 600),
        )
