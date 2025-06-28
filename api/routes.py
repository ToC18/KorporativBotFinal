import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from database.main import get_session
from database.models import Poll, PollOption, Vote

router = APIRouter()
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")


class OptionOut(BaseModel):
    id: int
    option_text: str
    votes_count: int
    model_config = ConfigDict(from_attributes=True)


class PollOut(BaseModel):
    id: int
    title: str
    status: bool
    options: List[OptionOut]
    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_class=HTMLResponse, summary="Показать страницу со списком всех опросов")
async def get_index_page(request: Request, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Poll).order_by(Poll.id.desc()))
    all_polls = result.scalars().all()
    return templates.TemplateResponse("index.html", {"request": request, "polls": all_polls})


@router.get("/report/{poll_id}/view", response_class=HTMLResponse, summary="Посмотреть веб-отчет по опросу")
async def get_web_report(request: Request, poll_id: int, session: AsyncSession = Depends(get_session)):
    logger.info(f"--- [ОТЧЕТ] Запрошен веб-отчет для опроса ID: {poll_id} ---")

    poll_result = await session.execute(select(Poll).filter(Poll.id == poll_id))
    poll = poll_result.scalar_one_or_none()

    if not poll:
        raise HTTPException(status_code=404, detail=f"Опрос с ID {poll_id} не найден.")

    participants_query = (
        select(Vote)
        .options(
            selectinload(Vote.user),
            selectinload(Vote.option)
        )
        .filter(Vote.poll_id == poll_id)
    )
    participants_result = await session.execute(participants_query)
    participants = participants_result.scalars().all()
    logger.info(f"[ОТЧЕТ] Найдено голосов в БД: {len(participants)}")

    options_query = select(PollOption).filter(PollOption.poll_id == poll_id).order_by(PollOption.id)
    options_result = await session.execute(options_query)
    options = options_result.scalars().all()

    total_votes = len(participants)
    chart_labels = json.dumps([opt.option_text for opt in options] if options else [])
    chart_values = json.dumps([opt.votes_count for opt in options] if options else [])

    context = {
        "request": request,
        "poll": poll,
        "total_votes": total_votes,
        "labels": chart_labels,
        "values": chart_values,
        "participants": participants
    }

    return templates.TemplateResponse("report.html", context)


@router.get("/polls", response_model=List[PollOut], summary="Получить все опросы в JSON")
async def get_all_polls_json(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Poll).options(selectinload(Poll.options)).order_by(Poll.id.desc())
    )
    return result.scalars().all()


@router.get("/polls/{poll_id}", response_model=PollOut, summary="Получить конкретный опрос в JSON")
async def get_poll_by_id_json(poll_id: int, session: AsyncSession = Depends(get_session)):
    poll = await session.get(Poll, poll_id, options=[selectinload(Poll.options)])
    if not poll:
        raise HTTPException(status_code=404, detail="Опрос не найден.")
    return poll


@router.put("/polls/{poll_id}/status", summary="Изменить статус опроса")
async def update_poll_status(poll_id: int, status: bool, session: AsyncSession = Depends(get_session)):
    poll = await session.get(Poll, poll_id)
    if not poll:
        raise HTTPException(status_code=404, detail="Опрос не найден.")
    poll.status = status
    await session.commit()
    return {"message": f"Статус опроса {poll_id} изменен на {status}."}