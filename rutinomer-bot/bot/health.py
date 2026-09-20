"""HTTP-эндпоинт для health-check и самопинг против засыпания.

Бесплатные хостинги (Render, Koyeb) требуют открытый порт и глушат процесс,
если по нему нет трафика. Поэтому: отдаем /health и сами себя дергаем.
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp
from aiohttp import web

log = logging.getLogger(__name__)


async def _health(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def start_health_server(port: int) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("Health-сервер поднят на порту %s", port)
    return runner


async def keepalive_loop(url: str, interval: int) -> None:
    """Пингует сам себя. Если хостинг все равно усыпляет - см. docs/DEPLOY.md,
    там про внешний пинг через cron-job.org, он надежнее.
    """
    target = f"{url}/health"
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(interval)
            try:
                async with session.get(target, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    log.debug("Keepalive %s -> %s", target, resp.status)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("Keepalive не дошел: %s", exc)
