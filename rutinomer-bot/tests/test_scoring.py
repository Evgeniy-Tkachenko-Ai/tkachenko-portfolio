"""Тесты на то, что можно проверить без сети: скоринг и чистка тире."""
from __future__ import annotations

import pytest

from bot.llm import Quiz, score_to_ten, strip_dashes


@pytest.mark.parametrize(
    "score, max_score, expected",
    [
        (0, 12, 0),
        (12, 12, 10),
        (6, 12, 5),
        (7, 12, 6),    # 5.83 -> 6
        (5, 12, 4),    # 4.17 -> 4
        (1, 8, 1),     # 1.25 -> 1
        (3, 8, 4),     # 3.75 -> 4
        (0, 0, 0),     # деление на ноль не роняет бота
    ],
)
def test_score_to_ten(score: int, max_score: int, expected: int) -> None:
    assert score_to_ten(score, max_score) == expected


def test_score_never_out_of_range() -> None:
    for max_score in range(1, 13):
        for score in range(max_score + 1):
            assert 0 <= score_to_ten(score, max_score) <= 10


def test_strip_dashes() -> None:
    assert strip_dashes("это — тест – да −") == "это - тест - да -"


def test_quiz_rejects_too_few_questions() -> None:
    with pytest.raises(Exception):
        Quiz.model_validate(
            {"questions": [{"q": "a", "options": [{"text": "x", "score": 0}]}]}
        )


def test_quiz_rejects_bad_score() -> None:
    question = {
        "q": "Как приходят заявки?",
        "options": [{"text": "руками", "score": 5}, {"text": "само", "score": 2}],
    }
    with pytest.raises(Exception):
        Quiz.model_validate({"questions": [question] * 4})


def test_quiz_accepts_valid() -> None:
    question = {
        "q": "Как приходят заявки?",
        "options": [{"text": "руками", "score": 0}, {"text": "само", "score": 2}],
    }
    quiz = Quiz.model_validate({"questions": [question] * 4})
    assert len(quiz.questions) == 4
