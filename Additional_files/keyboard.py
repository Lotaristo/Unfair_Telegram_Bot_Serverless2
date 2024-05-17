# Используемая клавиатура
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def start_game():
    builder = ReplyKeyboardBuilder()
    builder.button(text = 'Начать игру')
    return builder.as_markup(resize_keyboard = True, one_time_keyboard = True)


def generate_options_keyboard(answer_options, right_answer):
    builder = InlineKeyboardBuilder()
    for option in answer_options:
        builder.add(InlineKeyboardButton(text=option, callback_data="right_answer" if option == right_answer else "wrong_answer"))
    builder.adjust(1)

    return builder.as_markup()