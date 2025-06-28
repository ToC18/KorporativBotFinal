# KorpBot/config.py (ПОЛНАЯ ВЕРСИЯ)

import os
import logging

# Настраиваем логгер для этого модуля, чтобы видеть информацию при старте
logger = logging.getLogger(__name__)

# Читаем строку с ID администраторов из переменных окружения .env
# Если переменная ADMIN_IDS не найдена, по умолчанию будет пустая строка ""
admin_ids_str = os.getenv("ADMIN_IDS", "")

# Безопасно преобразуем строку в список целых чисел
try:
    # Разделяем строку по запятой, убираем пробелы, проверяем, что это число, и конвертируем
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in admin_ids_str.split(',') if admin_id.strip().isdigit()]
    if ADMIN_IDS:
        logger.info(f"Успешно загружен список ID администраторов: {ADMIN_IDS}")
    else:
        logger.warning("Список ID администраторов пуст. Админ-команды не будут доступны никому.")
except ValueError:
    logger.error("Критическая ошибка при чтении ADMIN_IDS. Проверьте формат в .env файле.")
    ADMIN_IDS = []


def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли переданный user_id ID администратора.
    :param user_id: Telegram ID пользователя.
    :return: True, если пользователь админ, иначе False.
    """
    return user_id in ADMIN_IDS