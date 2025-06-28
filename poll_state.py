from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from aiogram import types
from database.models import PollOption, Vote, Poll

async def start_new_poll(session: AsyncSession, question: str, options: list) -> int:
    """
    Создает новый опрос и добавляет его в базу данных.
    Возвращает ID созданного опроса.
    """
    try:
        new_poll = Poll(title=question)
        session.add(new_poll)
        await session.flush()

        for option_text in options:
            poll_option = PollOption(poll_id=new_poll.id, option_text=option_text, votes_count=0)
            session.add(poll_option)

        await session.commit()
        return new_poll.id
    except Exception as e:
        await session.rollback()
        print(f"Ошибка при создании опроса: {e}")
        raise


async def record_vote(session: AsyncSession, poll_id: int, option_id: int, user: types.User):
    """
    Сохраняет голос пользователя. Если пользователь уже голосовал - обновляет его голос.
    """
    try:
        # Ищем существующий голос пользователя в этом опросе
        existing_vote_result = await session.execute(
            select(Vote).filter_by(poll_id=poll_id, user_tg_id=user.id)
        )
        user_vote = existing_vote_result.scalars().first()

        if user_vote:
            # Если пользователь меняет свой выбор
            if user_vote.option_id != option_id:
                # Уменьшаем счетчик старого варианта
                old_option = await session.get(PollOption, user_vote.option_id)
                if old_option and old_option.votes_count > 0:
                    old_option.votes_count -= 1

                # Увеличиваем счетчик нового варианта
                new_option = await session.get(PollOption, option_id)
                if new_option:
                    new_option.votes_count += 1

                # Обновляем ID варианта в голосе
                user_vote.option_id = option_id
        else:
            # Пользователь голосует впервые в этом опросе
            new_vote = Vote(
                poll_id=poll_id,
                user_tg_id=user.id, # Используем ID из объекта User
                option_id=option_id,
            )
            session.add(new_vote)

            # Увеличиваем счетчик голосов для выбранного варианта
            option = await session.get(PollOption, option_id)
            if option:
                option.votes_count += 1

        await session.commit()
    except Exception as e:
        await session.rollback()
        print(f"Ошибка при сохранении голоса: {e}")
        raise
