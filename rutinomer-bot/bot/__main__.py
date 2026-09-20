"""Точка входа. Long polling - вебхук не нужен, меньше движущихся частей."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from .config import Config
from .db import Database
from .handlers import build_router
from .health import keepalive_loop, start_health_server
from .llm import Claude

log = logging.getLogger("bot")

COMMANDS = [
    BotCommand(command="start", description="Пройти диагностику"),
    BotCommand(command="help", description="Что тут вообще"),
    BotCommand(command="delete", description="Удалить мои данные"),
]


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.load()

    db = Database(config.db_path)
    await db.init()

    claude = Claude(config.anthropic_api_key, config.model)
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    # Эти объекты аiogram сам подставит в хендлеры по имени аргумента.
    dispatcher.workflow_data.update(db=db, claude=claude, config=config)
    dispatcher.include_router(build_router())

    background: list[asyncio.Task] = []
    runner = await start_health_server(config.port)
    if config.keepalive_url:
        background.append(
            asyncio.create_task(
                keepalive_loop(config.keepalive_url, config.keepalive_interval)
            )
        )
    else:
        log.info("KEEPALIVE_URL не задан, самопинг выключен")

    await bot.set_my_commands(COMMANDS)
    # Копим апдейты, пока лежали: ничего не теряем после перезапуска.
    log.info("Бот запущен, модель %s", config.model)
    try:
        await dispatcher.start_polling(bot, handle_signals=False)
    finally:
        for task in background:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await runner.cleanup()
        with contextlib.suppress(Exception):
            await claude.close()
        await bot.session.close()
        log.info("Остановился")


def main() -> int:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        return 0
    except RuntimeError as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
