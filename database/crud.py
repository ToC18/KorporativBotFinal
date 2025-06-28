from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .models import BotUser, Vote, Poll

async def get_or_create_user(session: AsyncSession, user_data: types.User) -> BotUser:
    result = await session.execute(select(BotUser).filter(BotUser.user_tg_id == user_data.id))
    db_user = result.scalar_one_or_none()

    if not db_user:
        db_user = BotUser(
            user_tg_id=user_data.id,
            username=user_data.username,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
        )
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)

    return db_user


async def get_user_completed_polls(session: AsyncSession, user_tg_id: int) -> list[Poll]:
    query = (
        select(Poll)
        .join(Vote, Vote.poll_id == Poll.id)
        .filter(Vote.user_tg_id == user_tg_id)
        .distinct()
        .order_by(Poll.created_at.desc())
    )
    result = await session.execute(query)
    return result.scalars().all()

# НОВАЯ ФУНКЦИЯ ДЛЯ РАССЫЛКИ
async def get_all_users(session: AsyncSession) -> list[BotUser]:
    """
    Возвращает список всех зарегистрированных пользователей.
    """
    query = select(BotUser)
    result = await session.execute(query)
    return result.scalars().all()