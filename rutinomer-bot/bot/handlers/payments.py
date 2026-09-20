"""Оплата повторной диагностики звездами Telegram.

Для цифровых товаров внутри Telegram это единственный разрешенный способ.
Ключевое: currency="XTR", provider_token пустой, amount - само число звезд.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery

from .. import keyboards as kb
from .. import texts
from ..config import Config
from ..db import Database
from ..states import Diag

log = logging.getLogger(__name__)
router = Router(name="payments")

PAYLOAD = "diagnostic_rerun_v1"


@router.callback_query(F.data == kb.CB_BUY)
async def send_invoice(call: CallbackQuery, config: Config) -> None:
    await call.answer()
    if call.message is None:
        return
    await call.message.answer_invoice(
        title=texts.INVOICE_TITLE,
        description=texts.INVOICE_DESCRIPTION,
        payload=PAYLOAD,
        currency="XTR",
        prices=kb.stars_price(config.price_stars),
        provider_token="",
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    """Ответить надо в пределах 10 секунд, иначе платеж отменится."""
    if query.invoice_payload != PAYLOAD:
        await query.answer(ok=False, error_message="Счет устарел. Начни заново: /start")
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def paid(
    message: Message, state: FSMContext, db: Database, config: Config
) -> None:
    """Товар выдаем только здесь: pre_checkout сам по себе оплату не гарантирует."""
    payment = message.successful_payment
    if payment is None:
        return
    fresh = await db.add_paid_credit(
        message.chat.id, payment.telegram_payment_charge_id, payment.total_amount
    )
    if not fresh:
        log.info("Повторный апдейт по платежу %s, пропускаю", payment.telegram_payment_charge_id)
        return

    if config.admin_chat_id:
        try:
            await message.bot.send_message(
                config.admin_chat_id,
                f"Оплата: {payment.total_amount} звезд от id {message.chat.id}",
            )
        except Exception:
            log.exception("Не смог уведомить об оплате")

    await state.clear()
    await state.set_state(Diag.niche)
    await message.answer(texts.PAYMENT_OK)


@router.message(Command("refund"))
async def refund(message: Message, db: Database, config: Config) -> None:
    """Возврат звезд. Только для Евгения: /refund <charge_id>"""
    if not config.admin_chat_id or message.chat.id != config.admin_chat_id:
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: /refund <user_id> <charge_id>")
        return
    _, raw_user, charge_id = parts
    try:
        ok = await message.bot.refund_star_payment(
            user_id=int(raw_user), telegram_payment_charge_id=charge_id
        )
    except Exception as exc:
        await message.answer(f"Не вышло: {exc}")
        return
    await message.answer("Возврат прошел" if ok else "Telegram вернул отказ")
