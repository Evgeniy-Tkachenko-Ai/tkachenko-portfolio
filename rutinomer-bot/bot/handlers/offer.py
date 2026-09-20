"""Шаг 5: оффер, сбор контакта, уведомление Евгению. Плюс свободные вопросы."""
from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from .. import texts
from ..config import Config
from ..db import Database
from ..llm import Claude
from ..states import Diag

log = logging.getLogger(__name__)
router = Router(name="offer")

OFFER_LABELS = {
    kb.CB_OFFER_CALC: "Расчет стоимости и сроков",
    kb.CB_OFFER_CONSULT: "Бесплатная консультация",
}


@router.callback_query(Diag.offer, F.data.in_(OFFER_LABELS.keys()))
async def picked_offer(
    call: CallbackQuery, state: FSMContext, config: Config
) -> None:
    await call.answer()
    if call.message is None or call.data is None:
        return
    await state.update_data(offer_type=OFFER_LABELS[call.data])
    await state.set_state(Diag.contact)
    await call.message.answer(
        texts.ASK_CONTACT_TEMPLATE.format(site=config.site_url),
        disable_web_page_preview=True,
    )


@router.message(Diag.contact, F.text)
async def got_contact(
    message: Message, state: FSMContext, db: Database, config: Config
) -> None:
    contact = (message.text or "").strip()[:1000]
    data = await state.get_data()
    user = message.from_user
    username = (user.username or "") if user else ""

    await db.save_lead(
        user_id=message.chat.id,
        username=username,
        offer_type=data.get("offer_type", "не указан"),
        contact=contact,
        niche=data.get("niche", ""),
        score10=data.get("score10"),
    )
    await _notify_admin(message, config, data, contact, username)

    await message.answer(texts.LEAD_SAVED)
    ps = texts.postscript(config.chat_url)
    if ps:
        await message.answer(ps, disable_web_page_preview=True)
    await state.set_state(Diag.done)


async def _notify_admin(
    message: Message,
    config: Config,
    data: dict,
    contact: str,
    username: str,
) -> None:
    """Лид в личку Евгению. Если не дошло - он все равно лежит в базе и /leads."""
    if not config.admin_chat_id:
        log.warning("ADMIN_CHAT_ID не задан, уведомление о лиде не отправлено")
        return
    handle = f"@{username}" if username else "без username"
    body = (
        "<b>Новый лид</b>\n\n"
        f"Кто: {html.escape(message.from_user.full_name if message.from_user else '')} "
        f"({handle}, id {message.chat.id})\n"
        f"Запрос: {html.escape(data.get('offer_type', 'не указан'))}\n"
        f"Оценка: {data.get('score10', '?')}/10\n"
        f"Ниша: {html.escape(str(data.get('niche', ''))[:600])}\n"
        f"Боль: {html.escape(str(data.get('pain', '')) or 'не сказал')}\n\n"
        f"Контакт и задача:\n{html.escape(contact)}"
    )
    try:
        await message.bot.send_message(
            config.admin_chat_id, body, parse_mode=ParseMode.HTML
        )
    except Exception:
        log.exception("Не смог отправить уведомление о лиде админу")


@router.message(Diag.offer, F.text)
@router.message(Diag.done, F.text)
async def freeform(message: Message, state: FSMContext, claude: Claude) -> None:
    """Человек не выбрал кнопку, а что-то спрашивает. Не дожимаем, отвечаем."""
    data = await state.get_data()
    try:
        answer = await claude.answer_freeform(
            data.get("niche", ""), data.get("score10"), (message.text or "")[:1000]
        )
    except Exception:
        log.exception("Не смог ответить на свободный вопрос")
        await message.answer(texts.LLM_ERROR)
        return
    await message.answer(answer)
