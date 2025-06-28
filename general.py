# --- START OF FILE general.py ---

from aiogram import types, Router, F

router = Router()

@router.message(F.text.lower() == 'привет')
async def greet_user(message: types.Message):
    await message.answer(f'Здравствуйте, {message.from_user.full_name}')

@router.message(F.text.lower() == 'id')
async def send_user_id(message: types.Message):
    await message.reply(f'Ваш ID: {message.from_user.id}')

# Этот хэндлер будет ловить любые другие текстовые сообщения
@router.message(F.text)
async def handle_other_text(message: types.Message):
    await message.answer("Я вас не понимаю. Используйте команду /help для списка команд.")