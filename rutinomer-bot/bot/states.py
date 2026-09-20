from aiogram.fsm.state import State, StatesGroup


class Diag(StatesGroup):
    """Шаги диалога. Порядок жесткий, как в брифе."""

    consent = State()   # шаг 0: согласие на обработку данных
    niche = State()     # шаг 1: чем занимается (открытый вопрос)
    pain = State()      # шаг 2: что бесит (открытый вопрос или "Не знаю")
    quiz = State()      # шаг 3: 4-6 вопросов кнопками
    offer = State()     # шаг 5: выбор оффера
    contact = State()   # сбор контакта
    done = State()      # свободные вопросы после диагностики
