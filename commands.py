import logging
from aiogram import types, Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from database import crud
from database.models import Poll, PollOption, Vote
from poll_state import start_new_poll, record_vote
from keyboards import (
    get_main_menu,
    create_poll_choice_keyboard,
    create_admin_poll_keyboard,
    create_voting_keyboard,
    create_results_keyboard,
    create_delete_confirm_keyboard,
)
from config import is_admin
# ИМПОРТИРУЕМ ОБЕ НАШИ ЗАДАЧИ
from tasks import notify_users_about_new_poll, broadcast_message_task

logger = logging.getLogger(__name__)
router = Router()


class DbSessionMiddleware:
    def __init__(self, session_pool):
        self.session_pool = session_pool

    async def __call__(self, handler, event, data):
        async with self.session_pool() as session:
            data["session"] = session
            return await handler(event, data)


async def get_poll_text_and_options(poll_id: int, session: AsyncSession) -> tuple[str, list[PollOption] | None]:
    query = select(Poll).options(selectinload(Poll.options)).filter(Poll.id == poll_id)
    poll = (await session.execute(query)).scalar_one_or_none()
    if not poll: return "Опрос не найден.", None
    total_votes = sum(opt.votes_count for opt in poll.options)
    text_lines = [f"<b>{poll.title}</b>\n", f"👥 Всего проголосовало: {total_votes}\n"]
    sorted_options = sorted(poll.options, key=lambda o: o.id)
    for option in sorted_options:
        percentage = (option.votes_count / total_votes * 100) if total_votes > 0 else 0
        text_lines.append(f"▫️ {option.option_text}: {option.votes_count} ({percentage:.1f}%)")
    return "\n".join(text_lines), sorted_options


class PollCreation(StatesGroup):
    waiting_for_question = State()
    waiting_for_options = State()


# НОВЫЕ СОСТОЯНИЯ ДЛЯ РАССЫЛКИ
class Broadcast(StatesGroup):
    waiting_for_message = State()


@router.message(Command("start"))
async def start(message: types.Message, session: AsyncSession):
    await crud.get_or_create_user(session, message.from_user)
    await message.answer(
        f"Здравствуйте, {message.from_user.first_name}! 👋\n\n"
        "Я корпоративный бот для проведения голосований.",
        reply_markup=get_main_menu()
    )


@router.message(Command("profile"))
async def show_profile(message: types.Message, session: AsyncSession):
    user = await crud.get_or_create_user(session, message.from_user)
    completed_polls = await crud.get_user_completed_polls(session, user.user_tg_id)

    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"<b>ID:</b> <code>{user.user_tg_id}</code>\n"
        f"<b>Имя:</b> {user.full_name}\n"
        f"<b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M')}\n"
    )

    if completed_polls:
        poll_titles = "\n".join([f"• <i>{poll.title}</i>" for poll in completed_polls])
        profile_text += f"\n\n✅ <b>Пройденные опросы:</b>\n{poll_titles}"
    else:
        profile_text += "\n\nВы еще не участвовали ни в одном опросе."

    await message.answer(profile_text, parse_mode="HTML")


@router.message(Command("webreports"))
async def get_web_interface_link(message: types.Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Эта команда доступна только администратору.")
    web_url = "http://localhost:8000/api/"
    await message.answer(f"🔗 Веб-интерфейс для просмотра всех опросов и отчетов доступен по ссылке:\n{web_url}")


@router.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "<b>Доступные команды:</b>\n"
        "/poll - Показать список активных опросов.\n"
        "/profile - Посмотреть ваш профиль.\n"
        "/site - Открыть сайт БелАЗ.\n"
        "/start - Перезапустить бота.\n\n"
        "<b>Для администраторов:</b>\n"
        "/webreports - Открыть все опросы.\n"
        "/newpoll - Создать новый опрос.\n"
        "/broadcast - Сделать рассылку всем пользователям.\n"  # <-- НОВЫЙ ПУНКТ
        "/list_polls - Управление опросами.",
        parse_mode="HTML"
    )


@router.message(Command("site", "website"))
async def site(message: types.Message):
    await message.answer("Перейдите на сайт: https://belaz.by")


@router.message(Command("poll"))
async def list_active_polls(message: types.Message, session: AsyncSession):
    result = await session.execute(select(Poll).filter_by(status=True).order_by(Poll.created_at.desc()))
    active_polls = result.scalars().all()
    if not active_polls:
        await message.answer("На данный момент активных опросов нет. 😴")
        return
    await message.answer("Выберите опрос для участия:", reply_markup=create_poll_choice_keyboard(active_polls))


@router.message(Command("newpoll"))
async def newpoll_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Эта команда доступна только администратору.")
    await message.answer("Введите вопрос для нового опроса:")
    await state.set_state(PollCreation.waiting_for_question)


@router.message(StateFilter(PollCreation.waiting_for_question))
async def newpoll_get_question(message: types.Message, state: FSMContext):
    await state.update_data(question=message.text)
    await message.answer("Отлично. Теперь введите варианты ответа через запятую.")
    await state.set_state(PollCreation.waiting_for_options)


@router.message(StateFilter(PollCreation.waiting_for_options))
async def newpoll_get_options(message: types.Message, state: FSMContext, session: AsyncSession):
    options = [opt.strip() for opt in message.text.split(",") if opt.strip()]
    if len(options) < 2:
        await message.answer("Нужно как минимум 2 варианта. Попробуйте еще раз.")
        return
    data = await state.get_data()
    question = data.get("question")
    poll_id = await start_new_poll(session, question, options)

    await message.answer(f"✅ Опрос \"{question}\" успешно создан с ID {poll_id}.")
    await state.clear()

    notify_users_about_new_poll.delay(poll_id)
    await message.answer("Запущена рассылка уведомлений о новом опросе...")


# НОВЫЕ ОБРАБОТЧИКИ ДЛЯ РАССЫЛКИ
@router.message(Command("broadcast"))
async def broadcast_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Эта команда доступна только администратору.")
    await message.answer("Введите текст сообщения, которое вы хотите отправить всем пользователям:")
    await state.set_state(Broadcast.waiting_for_message)


@router.message(StateFilter(Broadcast.waiting_for_message))
async def broadcast_get_message(message: types.Message, state: FSMContext):
    # Запускаем фоновую задачу для рассылки сообщения
    # Передаем текст сообщения как аргумент
    broadcast_message_task.delay(message.text)
    await message.answer("✅ Рассылка запущена! Пользователи получат ваше сообщение в фоновом режиме.")
    await state.clear()


@router.callback_query(F.data.startswith("poll_"))
async def send_custom_poll(callback: types.CallbackQuery, session: AsyncSession):
    poll_id = int(callback.data.split("_")[1])
    poll_text, options = await get_poll_text_and_options(poll_id, session)
    if not options:
        await callback.answer(poll_text, show_alert=True)
        return
    await callback.message.answer(text=poll_text, reply_markup=create_voting_keyboard(options), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("vote_"))
async def handle_vote(callback: types.CallbackQuery, session: AsyncSession):
    option_id = int(callback.data.split("_")[1])
    option = await session.get(PollOption, option_id)
    if not option:
        await callback.answer("Этот вариант ответа больше не существует.", show_alert=True)
        return

    await crud.get_or_create_user(session, callback.from_user)
    await record_vote(session, option.poll_id, option_id, callback.from_user)

    new_text, _ = await get_poll_text_and_options(option.poll_id, session)
    try:
        await callback.message.edit_text(text=new_text, reply_markup=create_results_keyboard(option.poll_id),
                                         parse_mode="HTML")
        await callback.answer("Ваш голос учтен!")
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение: {e}")
        await callback.answer("Ваш голос учтен!")


@router.callback_query(F.data.startswith("results_"))
async def refresh_results(callback: types.CallbackQuery, session: AsyncSession):
    poll_id = int(callback.data.split("_")[1])
    new_text, options = await get_poll_text_and_options(poll_id, session)
    if not options:
        await callback.answer("Опрос не найден.", show_alert=True)
        return

    try:
        user_vote_check = await session.execute(
            select(Vote).filter_by(poll_id=poll_id, user_tg_id=callback.from_user.id))
        voted = user_vote_check.scalar_one_or_none() is not None

        keyboard = create_results_keyboard(poll_id) if voted else create_voting_keyboard(options)
        await callback.message.edit_text(text=new_text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("Результаты обновлены.")
    except Exception as e:
        logger.warning(f"Не удалось обновить результаты: {e}")
        await callback.answer("Результаты уже актуальны.")


@router.message(Command("list_polls"))
async def list_all_polls_admin(message: types.Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Эта команда доступна только администратору.")

    result = await session.execute(select(Poll).order_by(Poll.created_at.desc()))
    all_polls = result.scalars().all()

    if not all_polls:
        await message.answer("В базе данных еще нет ни одного опроса.")
        return

    await message.answer("<b>Список всех опросов для управления:</b>", parse_mode="HTML")
    for poll in all_polls:
        status_emoji = "🟢 Активен" if poll.status else "🔴 Завершен"
        poll_text = f"<b>ID: {poll.id}</b> - {poll.title}\n<i>Статус: {status_emoji}</i>"
        await message.answer(poll_text, reply_markup=create_admin_poll_keyboard(poll), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_poll_"))
async def manage_poll_status(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ запрещен.", show_alert=True)

    parts = callback.data.split("_")
    action = parts[2]
    poll_id = int(parts[3])

    poll_to_update = await session.get(Poll, poll_id)
    if not poll_to_update:
        return await callback.answer("Опрос не найден.", show_alert=True)

    poll_to_update.status = (action == "activate")
    await session.commit()
    await callback.answer(f"Опрос {'активирован' if poll_to_update.status else 'завершен'}.")

    status_emoji = "🟢 Активен" if poll_to_update.status else "🔴 Завершен"
    poll_text = f"<b>ID: {poll_to_update.id}</b> - {poll_to_update.title}\n<i>Статус: {status_emoji}</i>"
    await callback.message.edit_text(poll_text, reply_markup=create_admin_poll_keyboard(poll_to_update),
                                     parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_report_"))
async def send_web_report_link(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ запрещен.", show_alert=True)

    poll_id = int(callback.data.split("_")[2])
    report_url = f"http://localhost:8000/api/report/{poll_id}/view"
    await callback.message.answer(f"Ссылка на веб-отчет по опросу ID {poll_id}:\n{report_url}")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_ask_"))
async def ask_delete_poll(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ запрещен.", show_alert=True)

    poll_id = int(callback.data.split("_")[3])
    await callback.message.edit_text(
        f"Вы уверены, что хотите удалить опрос ID {poll_id}?\n"
        "<b>Это действие необратимо и удалит всю связанную статистику!</b>",
        reply_markup=create_delete_confirm_keyboard(poll_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_confirm_"))
async def confirm_delete_poll(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ запрещен.", show_alert=True)

    poll_id = int(callback.data.split("_")[3])
    poll_to_delete = await session.get(Poll, poll_id)
    if poll_to_delete:
        await session.delete(poll_to_delete)
        await session.commit()
        await callback.message.edit_text(f"✅ Опрос ID {poll_id} был успешно удален.")
    else:
        await callback.message.edit_text(f"⚠️ Опрос ID {poll_id} уже был удален ранее.")

    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_cancel_"))
async def cancel_delete_poll(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ запрещен.", show_alert=True)

    poll_id = int(callback.data.split("_")[3])
    poll = await session.get(Poll, poll_id)
    if not poll:
        await callback.message.edit_text("Опрос был удален.")
        return

    status_emoji = "🟢 Активен" if poll.status else "🔴 Завершен"
    poll_text = f"<b>ID: {poll.id}</b> - {poll.title}\n<i>Статус: {status_emoji}</i>"
    await callback.message.edit_text(poll_text, reply_markup=create_admin_poll_keyboard(poll),
                                     parse_mode="HTML")
    await callback.answer("Удаление отменено.")
