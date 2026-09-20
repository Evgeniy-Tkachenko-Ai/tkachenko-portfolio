from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)

CB_CONSENT = "consent:yes"
CB_PRIVACY = "consent:privacy"
CB_PAIN_SKIP = "pain:skip"
CB_QUIZ_PREFIX = "q"          # q:<индекс вопроса>:<индекс варианта>
CB_OFFER_CALC = "offer:calc"
CB_OFFER_CONSULT = "offer:consult"
CB_BUY = "buy:again"


def consent_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поехали", callback_data=CB_CONSENT)],
            [InlineKeyboardButton(text="Что за данные?", callback_data=CB_PRIVACY)],
        ]
    )


def pain_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Не знаю", callback_data=CB_PAIN_SKIP)]
        ]
    )


def quiz_kb(question_index: int, options: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=text[:100],
                callback_data=f"{CB_QUIZ_PREFIX}:{question_index}:{i}",
            )
        ]
        for i, text in enumerate(options)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def offer_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Заказать расчет", callback_data=CB_OFFER_CALC)],
            [
                InlineKeyboardButton(
                    text="Бесплатная консультация", callback_data=CB_OFFER_CONSULT
                )
            ],
        ]
    )


def paywall_kb(stars: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Пройти еще раз - {stars} звезд", callback_data=CB_BUY
                )
            ]
        ]
    )


def stars_price(stars: int) -> list[LabeledPrice]:
    """Для XTR amount - это само количество звезд, без домножения на 100."""
    return [LabeledPrice(label="Диагностика", amount=stars)]
