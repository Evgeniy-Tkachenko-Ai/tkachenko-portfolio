"""Шаг 0: согласие, старт, развилка бесплатно/платно."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from .. import texts
from ..config import Config
from ..db import Database
from ..states import Diag

router = Router(name="start")


async def open_diagnostic(
    message: Message, state: FSMContext, db: Database, config: Config
) -> None:
    """Пускает в тест или показывает пейволл."""
    allowed, _is_free = await db.can_start(message.chat.id)
    if not allowed:
        await state.clear()
        await message.answer(
            texts.PAYWALL_TEMPLATE.format(stars=config.price_stars),
            reply_markup=kb.paywall_kb(config.price_stars),
        )
        return
    await state.set_state(Diag.niche)
    await message.answer(texts.GREETING)


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, db: Database, config: Config
) -> None:
    user = message.from_user
    if user is None:
        return
    await db.upsert_user(
        user.id, user.username or "", user.full_name or ""
    )
    await state.clear()
    if await db.has_consent(user.id):
        await open_diagnostic(message, state, db, config)
        return
    await state.set_state(Diag.consent)
    await message.answer(texts.CONSENT, reply_markup=kb.consent_kb())


@router.callback_query(F.data == kb.CB_PRIVACY)
async def show_privacy(call: CallbackQuery) -> None:
    await call.answer()
    if call.message:
        await call.message.answer(texts.PRIVACY, reply_markup=kb.consent_kb())


@router.callback_query(F.data == kb.CB_CONSENT)
async def give_consent(
    call: CallbackQuery, state: FSMContext, db: Database, config: Config
) -> None:
    await call.answer()
    if call.from_user is None or call.message is None:
        return
    await db.set_consent(call.from_user.id)
    await open_diagnostic(call.message, state, db, config)


@router.message(Command("delete"))
async def cmd_delete(message: Message, state: FSMContext, db: Database) -> None:
    """Право на удаление. Обещали в тексте согласия - значит работает."""
    user = message.from_user
    if user is None:
        return
    await state.clear()
    await db.forget_user(user.id)
    await message.answer(texts.DELETED)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.RESTART_HINT)


@router.message(Command("whoami"))
async def cmd_whoami(message: Message) -> None:
    """Чтобы Евгений узнал свой chat_id для ADMIN_CHAT_ID."""
    await message.answer(f"Твой chat_id: {message.chat.id}")
