from aiogram import Router

from . import admin, diagnostic, offer, payments, start


def build_router() -> Router:
    """Порядок важен: служебные команды и платежи раньше общих хендлеров."""
    router = Router(name="root")
    router.include_router(admin.router)
    router.include_router(payments.router)
    router.include_router(start.router)
    router.include_router(diagnostic.router)
    router.include_router(offer.router)
    return router
