import asyncio
import logging
import sys
import os

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
import redis.asyncio as redis

# Импортируем роутеры и middleware
from commands import router as commands_router, DbSessionMiddleware
from general import router as general_router
from database.main import init_models, async_session

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

if not BOT_TOKEN:
    logger.critical("Ошибка: Необходимо установить переменную окружения BOT_TOKEN")
    sys.exit("Ошибка: BOT_TOKEN не найден")

async def main():
    logger.info(f"Подключение к Redis: {REDIS_HOST}:{REDIS_PORT}")
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        await redis_client.ping()
        logger.info("Успешное подключение к Redis.")
    except Exception as e:
        logger.critical(f"Не удалось подключиться к Redis: {e}")
        sys.exit("Ошибка подключения к Redis")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    storage = RedisStorage(redis=redis_client)
    dp = Dispatcher(storage=storage)

    # Этот middleware будет создавать сессию БД для каждого запроса в commands_router
    commands_router.message.middleware(DbSessionMiddleware(session_pool=async_session))
    commands_router.callback_query.middleware(DbSessionMiddleware(session_pool=async_session))

    logger.info("Регистрация роутеров...")
    dp.include_router(commands_router)
    dp.include_router(general_router)
    logger.info("Роутеры зарегистрированы.")

    logger.info("Инициализация базы данных...")
    await init_models()
    logger.info("БД инициализирована.")

    me = await bot.get_me()
    logger.info(f"Бот запущен! ID: {me.id}, Имя: @{me.username}")

    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Запуск получения обновлений...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}", exc_info=True)