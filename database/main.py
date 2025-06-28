# KorpBot/database/main.py (ФИНАЛЬНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ)

import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .models import Base
from dotenv import load_dotenv
load_dotenv()
# 1. ПОЛУЧАЕМ URL ИЗ ПЕРЕМЕННОЙ ОКРУЖЕНИЯ, КОТОРУЮ ПЕРЕДАЕТ DOCKER COMPOSE
DATABASE_URL = os.getenv("DATABASE_URL")

# 2. ПРОВЕРЯЕМ, ЧТО ПЕРЕМЕННАЯ ПОЛУЧЕНА
if not DATABASE_URL:
    # Если переменная не найдена, программа аварийно завершится с понятной ошибкой
    sys.exit("Критическая ошибка: Переменная окружения DATABASE_URL не установлена!")

# 3. СОЗДАЕМ "ДВИЖОК" С ИСПОЛЬЗОВАНИЕМ ПОЛУЧЕННОЙ ПЕРЕМЕННОЙ
engine = create_async_engine(DATABASE_URL)

# --- Остальной код остается без изменений ---

# Создаем фабрику сессий
async_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

async def init_models():
    """
    Создает все таблицы в базе данных на основе моделей SQLAlchemy.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncSession:
    """
    Зависимость для FastAPI для получения сессии базы данных.
    """
    async with async_session() as session:
        yield session