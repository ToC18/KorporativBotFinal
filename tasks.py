import asyncio
import os
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties  # <-- ИСПРАВЛЕНИЕ: Добавлен импорт
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from worker import celery_app
from database.main import async_session
from database.models import Poll
from database import crud

logger = logging.getLogger(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")


@celery_app.task
def notify_users_about_new_poll(poll_id: int):
    logger.info(f"Запущена задача на уведомление о новом опросе ID: {poll_id}")
    asyncio.run(send_notifications(poll_id))


async def send_notifications(poll_id: int):
    if not BOT_TOKEN:
        logger.error("Не найден BOT_TOKEN в задаче рассылки. Рассылка отменена.")
        return

    # ИСПРАВЛЕНИЕ: Обновлен синтаксис инициализации бота
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    poll_title = ""
    users_to_notify = []

    async with async_session() as session:
        poll = await session.get(Poll, poll_id)
        if not poll:
            logger.error(f"Опрос ID {poll_id} не найден в БД. Рассылка отменена.")
            await bot.session.close()
            return
        poll_title = poll.title
        users_to_notify = await crud.get_all_users(session)

    if not users_to_notify:
        logger.warning("Нет пользователей для уведомления.")
        await bot.session.close()
        return

    logger.info(f"Начинается рассылка по опросу '{poll_title}' для {len(users_to_notify)} пользователей.")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🙋‍♂️ Пройти опрос", callback_data=f"poll_{poll_id}")]
    ])

    successful_sends = 0
    failed_sends = 0

    for user in users_to_notify:
        try:
            await bot.send_message(
                chat_id=user.user_tg_id,
                text=f"📢 <b>Новый опрос!</b>\n\n- <i>{poll_title}</i>\n\nПримите участие, ваше мнение важно!",
                reply_markup=keyboard
            )
            successful_sends += 1
            await asyncio.sleep(0.1)
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logger.warning(f"Не удалось отправить сообщение пользователю {user.user_tg_id}: {e}")
            failed_sends += 1
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при отправке пользователю {user.user_tg_id}: {e}")
            failed_sends += 1

    logger.info(f"Рассылка завершена. Успешно: {successful_sends}, Ошибок: {failed_sends}")
    await bot.session.close()


@celery_app.task
def broadcast_message_task(message_text: str):
    logger.info("Запущена задача на массовую рассылку сообщения.")
    asyncio.run(send_broadcast(message_text))


async def send_broadcast(message_text: str):
    if not BOT_TOKEN:
        logger.error("Не найден BOT_TOKEN в задаче рассылки. Рассылка отменена.")
        return

    # ИСПРАВЛЕНИЕ: Обновлен синтаксис инициализации бота
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    users_to_notify = []

    async with async_session() as session:
        users_to_notify = await crud.get_all_users(session)

    if not users_to_notify:
        logger.warning("Нет пользователей для рассылки.")
        await bot.session.close()
        return

    logger.info(f"Начинается рассылка сообщения для {len(users_to_notify)} пользователей.")

    successful_sends = 0
    failed_sends = 0

    for user in users_to_notify:
        try:
            await bot.send_message(chat_id=user.user_tg_id, text=message_text)
            successful_sends += 1
            await asyncio.sleep(0.1)
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logger.warning(f"Не удалось отправить сообщение пользователю {user.user_tg_id}: {e}")
            failed_sends += 1
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при отправке пользователю {user.user_tg_id}: {e}")
            failed_sends += 1

    logger.info(f"Массовая рассылка завершена. Успешно: {successful_sends}, Ошибок: {failed_sends}")
    await bot.session.close()