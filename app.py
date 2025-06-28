# KorpBot/app.py

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from api.routes import router as poll_router

app = FastAPI(title="PollBot API")

# Добавляем наш роутер с эндпоинтами
app.include_router(poll_router, prefix="/api")

# --- НОВЫЙ РЕДИРЕКТ ---
@app.get("/")
def read_root():
    """Редирект с главной страницы на список опросов."""
    return RedirectResponse(url="/api/")