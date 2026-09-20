"""Шаги 1-4: ниша, боль, тест кнопками, результат."""
from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from .. import texts
from ..config import Config
from ..db import Database
from ..llm import Claude, score_to_ten
from ..states import Diag

log = logging.getLogger(__name__)
router = Router(name="diagnostic")

MIN_NICHE_LEN = 12
VAGUE = {"бизнес", "торговля", "услуги", "продажи", "работа", "ип", "магазин"}


def _is_too_vague(text: str) -> bool:
    cleaned = text.strip().lower().strip(".,!")
    return len(cleaned) < MIN_NICHE_LEN or cleaned in VAGUE


async def _send_question(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions: list[dict[str, Any]] = data["questions"]
    index: int = data["q_index"]
    question = questions[index]
    header = f"Вопрос {index + 1} из {len(questions)}\n\n{question['q']}"
    await message.answer(
        header,
        reply_markup=kb.quiz_kb(index, [o["text"] for o in question["options"]]),
    )


# --- шаг 1: ниша -----------------------------------------------------
@router.message(Diag.niche, F.text)
async def got_niche(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    data = await state.get_data()
    if _is_too_vague(text) and not data.get("niche_retried"):
        # Уточняем ровно один раз, как в брифе.
        await state.update_data(niche_retried=True, niche=text)
        await message.answer(texts.NICHE_TOO_SHORT)
        return
    previous = str(data.get("niche", "")).strip()
    if data.get("niche_retried") and previous and previous.lower().strip(".,!") not in VAGUE:
        # Первый ответ был коротким, но содержательным - склеиваем.
        # Если это было просто "бизнес" - выкидываем, толку ноль.
        text = f"{previous}. {text}".strip(". ")
    await state.update_data(niche=text[:1500])
    await state.set_state(Diag.pain)
    await message.answer(texts.PAIN_QUESTION, reply_markup=kb.pain_kb())


# --- шаг 2: боль -----------------------------------------------------
async def _start_quiz(
    message: Message, state: FSMContext, db: Database, claude: Claude
) -> None:
    data = await state.get_data()
    niche = data.get("niche", "")
    pain = data.get("pain", "")
    await message.answer(texts.BUILDING_QUIZ)
    try:
        quiz = await claude.generate_quiz(niche, pain)
    except Exception:
        log.exception("Не смог сгенерировать тест")
        await state.set_state(Diag.pain)
        await message.answer(texts.LLM_ERROR)
        return

    # Попытку списываем только когда тест реально сгенерирован, иначе человек
    # потеряет бесплатный проход из-за нашей ошибки.
    was_free = await db.consume_attempt(message.chat.id)
    await state.set_state(Diag.quiz)
    await state.update_data(
        questions=[q.model_dump() for q in quiz.questions],
        q_index=0,
        answers=[],
        was_free=was_free,
    )
    await _send_question(message, state)


@router.message(Diag.pain, F.text)
async def got_pain(
    message: Message, state: FSMContext, db: Database, claude: Claude
) -> None:
    await state.update_data(pain=(message.text or "").strip()[:1500])
    await _start_quiz(message, state, db, claude)


@router.callback_query(Diag.pain, F.data == kb.CB_PAIN_SKIP)
async def skip_pain(
    call: CallbackQuery, state: FSMContext, db: Database, claude: Claude
) -> None:
    await call.answer()
    if call.message is None:
        return
    await state.update_data(pain="")
    await _start_quiz(call.message, state, db, claude)


# --- шаг 3: тест -----------------------------------------------------
@router.callback_query(Diag.quiz, F.data.startswith(f"{kb.CB_QUIZ_PREFIX}:"))
async def got_answer(
    call: CallbackQuery,
    state: FSMContext,
    db: Database,
    claude: Claude,
    config: Config,
) -> None:
    await call.answer()
    if call.message is None or call.data is None:
        return

    _, raw_q, raw_o = call.data.split(":")
    q_index, o_index = int(raw_q), int(raw_o)

    data = await state.get_data()
    questions: list[dict[str, Any]] = data.get("questions", [])
    current: int = data.get("q_index", 0)

    # Защита от двойных тапов и от кнопок из прошлого прохождения.
    if q_index != current or q_index >= len(questions):
        return

    question = questions[q_index]
    if o_index >= len(question["options"]):
        return
    option = question["options"][o_index]

    answers: list[dict[str, Any]] = data.get("answers", [])
    answers.append(
        {"q": question["q"], "answer": option["text"], "score": option["score"]}
    )

    # Убираем кнопки у отвеченного вопроса, чтобы не тыкали второй раз.
    try:
        await call.message.edit_text(
            f"{question['q']}\n\nТвой ответ: {option['text']}"
        )
    except Exception:  # сообщение могло быть удалено, это не критично
        log.debug("Не смог отредактировать вопрос", exc_info=True)

    next_index = q_index + 1
    await state.update_data(answers=answers, q_index=next_index)

    if next_index < len(questions):
        await _send_question(call.message, state)
        return

    await _finish(call.message, state, db, claude, config)


# --- шаг 4: результат ------------------------------------------------
async def _finish(
    message: Message,
    state: FSMContext,
    db: Database,
    claude: Claude,
    config: Config,
) -> None:
    data = await state.get_data()
    answers: list[dict[str, Any]] = data.get("answers", [])
    questions: list[dict[str, Any]] = data.get("questions", [])

    score = sum(a["score"] for a in answers)
    # Максимум считаем по лучшему варианту каждого вопроса, а не по 2 * N:
    # модель иногда не дает вариант на 2 балла, и тогда 2 * N наврет.
    max_score = sum(max(o["score"] for o in q["options"]) for q in questions)
    score10 = score_to_ten(score, max_score)

    await message.answer(texts.COUNTING)
    try:
        result = await claude.generate_result(
            data.get("niche", ""),
            data.get("pain", ""),
            answers,
            score,
            max_score,
            score10,
        )
    except Exception:
        log.exception("Не смог сгенерировать результат")
        await message.answer(texts.LLM_ERROR)
        return

    run_id = await db.save_run(
        user_id=message.chat.id,
        niche=data.get("niche", ""),
        pain=data.get("pain", ""),
        answers=answers,
        score=score,
        max_score=max_score,
        score10=score10,
        paid=not data.get("was_free", True),
    )

    await message.answer(result)
    await state.set_state(Diag.offer)
    await state.update_data(score10=score10, run_id=run_id)
    await message.answer(texts.OFFER, reply_markup=kb.offer_kb())
