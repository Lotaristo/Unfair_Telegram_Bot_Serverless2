from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram import F, Router

from Additional_files import keyboard as kb
from Additional_files.quiz_data import quiz_data
from database import pool, execute_update_query, execute_select_query

router = Router()


# Запуск бота, команда /start
@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        f'Привет, {message.from_user.first_name}. Нажми на кнопку, чтобы начать игру, или напиши "quiz".\nДля просмотра статистики по всем игрокам, используй команду "/info"',
        reply_markup=kb.start_game())


# Начало игры, команда /quiz
@router.message(F.text == "Начать игру")
@router.message(Command("quiz"))
async def cmd_quiz(message: Message):
    # Обнуляем количество правильных ответов перед началом новой игры
    await reset_correct_answers(message.from_user.id)

    # Выводим сообщение
    await message.answer(
        f"Привет, игрок! Сегодня у тебя есть уникальная возможность сыграть в небольшую игру и постараться ответить на 10 вопросов. Только не ожидай, что игра будет честной, а ответы очевидными. Удачи!")

    # Вставляем картинку
    photo_url = "https://storage.yandexcloud.net/image115185194/doge-%D0%BF%D0%B0%D0%B7%D0%B7%D0%BB.jpeg"
    await message.answer_photo(photo=photo_url,
                               caption="Отвечать на вопросы примерно так же интересно, как складывать данный паззл, только занимает немного меньше времени:)")

    # Запускаем первый вопрос
    await new_quiz(message)


# Получение статистики по игрокам
@router.message(Command('info'))
async def show_info(message: Message):
    await get_info()


# Выбор ответа
@router.callback_query(lambda x: x.data in ["right_answer", "wrong_answer"])
async def get_answer(callback: CallbackQuery):
    user_id = callback.from_user.id

    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        reply_markup=None)

    if callback.data == "right_answer":
        await callback.message.answer("Поздравляю, ты угадал!")
        await add_correct_answer(user_id)  # Добавляем правильный ответ в базу данных
    else:
        await callback.message.answer("Увы, но нет!")

    current_question_index = await get_quiz_index(user_id)

    # Обновление номера текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(user_id, current_question_index)

    if current_question_index < len(quiz_data):
        await get_question(callback.message, user_id)
    else:
        await callback.message.answer(
            f"Это был последний вопрос. Поздравляю с окончанием! Надеюсь, тебе понравилось :)\nТвой итоговый счет: {await get_current_score(user_id)} баллов, максимальный - {await get_max_score(user_id)} баллов.")


# Обновление таблицы
async def new_quiz(message):
    user_id = message.from_user.id
    current_question_index = 0
    await update_quiz_index(user_id, current_question_index)
    await get_question(message, user_id)


# Вопрос
async def get_question(message, user_id):
    # Запрашиваем из базы текущий индекс для вопроса
    current_question_index = await get_quiz_index(user_id)
    # Получаем индекс правильного ответа для текущего вопроса
    correct_index = quiz_data[current_question_index]['correct_option']
    opts = quiz_data[current_question_index]['options']

    kb_options = kb.generate_options_keyboard(opts, opts[correct_index])
    # Отправляем в чат сообщение с вопросом, прикрепляем сгенерированные кнопки
    await message.answer(f"{quiz_data[current_question_index]['question']}", reply_markup=kb_options)


# Получение данных из таблицы
async def get_quiz_index(user_id):
    get_user_index = f"""
            DECLARE $user_id AS Uint64;

            SELECT question_index
            FROM `quiz_state`
            WHERE user_id == $user_id;
        """

    results = execute_select_query(pool, get_user_index, user_id=user_id)

    if len(results) == 0:
        return 0
    if results[0]["question_index"] is None:
        return 0
    return results[0]["question_index"]


# Обновление таблицы
async def update_quiz_index(user_id, question_index):
    set_quiz_state = f"""
        DECLARE $user_id AS Uint64;
        DECLARE $question_index AS Uint64;

        UPSERT INTO `quiz_state` (`user_id`, `question_index`)
        VALUES ($user_id, $question_index);
    """

    execute_update_query(pool, set_quiz_state, user_id=user_id, question_index=question_index)


# Добавление правильного ответа в таблицу
async def add_correct_answer(user_id):
    set_correct_answers = """
        DECLARE $user_id AS Uint64;

        UPDATE quiz_state
        SET `correct_answers_current` = `correct_answers_current` + 1
        WHERE user_id == $user_id;
    """

    compare_scores = """
        DECLARE $user_id AS Uint64;

        SELECT CASE WHEN `correct_answers_current` >= `correct_answers_max` THEN 1 ELSE 0 END AS res
        FROM `quiz_state`
        WHERE `user_id` == $user_id;
    """
    update_max_score = """
        DECLARE $user_id AS Uint64;

        UPDATE `quiz_state`
        SET `correct_answers_max` = correct_answers_current
        WHERE `user_id` == $user_id;
    """

    execute_update_query(pool, set_correct_answers, user_id=user_id)
    results = execute_select_query(pool, compare_scores, user_id=user_id)
    if results[0][0] == 1:
        execute_update_query(pool, update_max_score, user_id=user_id)


# Получение максимального количества правильных ответов из таблицы
async def get_max_score(user_id):
    get_score = f"""
                DECLARE $user_id AS Uint64;

                SELECT correct_answers_max
                FROM `quiz_state`
                WHERE user_id == $user_id;
            """

    results = execute_select_query(pool, get_score, user_id=user_id)

    if results:
        return results[0][0]
    else:
        return 0


# Получение текущего количества правильных ответов из таблицы
async def get_current_score(user_id):
    get_score = f"""
                DECLARE $user_id AS Uint64;

                SELECT correct_answers_current
                FROM `quiz_state`
                WHERE user_id == $user_id;
            """

    results = execute_select_query(pool, get_score, user_id=user_id)

    if results:
        return results[0][0]
    else:
        return 0


# Получение статистики из таблицы
async def get_info():
    get_score = f"""
                SELECT user_id, correct_answers_max
                FROM `quiz_state`;
            """

    results = execute_select_query(pool, get_score)

    return results


# Обнуление количества правильных ответов в таблице перед началом новой игры
async def reset_correct_answers(user_id):
    set_correct_answers = """
        DECLARE $user_id AS Uint64;

        UPSERT INTO `quiz_state` (`user_id`, `correct_answers_current`)
        VALUES ($user_id, 0);
    """

    execute_update_query(pool, set_correct_answers, user_id=user_id)


