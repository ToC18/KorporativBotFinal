import os
import logging
import sys
from celery import Celery
from celery.signals import after_setup_logger
from dotenv import load_dotenv

load_dotenv()

# --- ИСПРАВЛЕНИЕ: Каноническая настройка логирования для Celery ---
@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    """
    Эта функция вызывается Celery для настройки логгера.
    Она перенаправляет все логи из worker'а в стандартный вывод,
    чтобы мы могли их видеть через 'docker-compose logs'.
    """
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Используем sys.stdout, чтобы логи шли в консоль контейнера
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
# ---

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

celery_app = Celery(
    'worker',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['tasks']
)

celery_app.conf.update(
    result_expires=3600,
)

if __name__ == '__main__':
    celery_app.start()
