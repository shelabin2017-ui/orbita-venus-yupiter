import asyncio

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from .config import Config
from .db import User
from .keyboards import admin, admin_back

r = Router()


class BroadcastState(StatesGroup):
    content = State()


def about_keyboard(config: Config):
    rows = []
    if config.author_url:
        rows.append([InlineKeyboardButton(text="👤 Автор проекта", url=config.author_url)])
    if config.author_tiktok_url:
        rows.append([InlineKeyboardButton(text="🎵 TikTok автора", url=config.author_tiktok_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def about_text(config: Config) -> str:
    author = config.author_name or "Автор проекта"
    return (
        "🌌 <b>Орбита — Венера-Юпитер</b>\n\n"
        "Это бот для знакомств, общения и новых совпадений — без лишнего шума.\n\n"
        f"✨ Проект создан: <b>{author}</b>.\n"
        "Здесь автор может делиться новостями, идеями и полезным контентом, "
        "не превращая знакомства в рекламную ленту."
    )


@r.message(F.text == "🌌 О проекте")
async def about_project(m: Message, config: Config):
    await m.answer(about_text(config), reply_markup=about_keyboard(config))


@r.callback_query(F.data == "adm:broadcast")
async def broadcast_start(c: CallbackQuery, config: Config, state: FSMContext):
    if c.from_user.id not in config.admin_ids:
        return await c.answer()
    await state.set_state(BroadcastState.content)
    await c.message.answer(
        "📢 <b>Рассылка</b>\n\n"
        "Пришлите одним сообщением текст, фото, видео или другой контент.\n"
        "Он будет отправлен зарегистрированным пользователям без изменения содержания.\n\n"
        "❌ Для отмены отправьте /cancel."
    )
    await c.answer()


@r.message(BroadcastState.content, F.text == "/cancel")
async def broadcast_cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Рассылка отменена.", reply_markup=admin())


@r.message(BroadcastState.content)
async def broadcast_send(m: Message, state: FSMContext, db, config: Config):
    if m.from_user.id not in config.admin_ids:
        await state.clear()
        return

    await state.clear()
    async with db.session() as s:
        users = (
            await s.execute(
                select(User.tg_id).where(
                    User.tg_id.is_not(None),
                    User.is_banned.is_(False),
                    User.deleted_at.is_(None),
                )
            )
        ).scalars().all()

    sent = 0
    failed = 0
    for tg_id in users:
        try:
            await m.copy_to(tg_id)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await m.answer(
        "📢 <b>Рассылка завершена</b>\n\n"
        f"✅ Доставлено: <b>{sent}</b>\n"
        f"⚠️ Не доставлено: <b>{failed}</b>",
        reply_markup=admin(),
    )
