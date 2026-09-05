from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select, or_

from .db import User, Match
from .keyboards import match_profile, matches_actions
from .services import get_user, public_photos

r = Router()


def profile_text(u: User) -> str:
    username = f"@{u.username}" if u.username else "Username не указан"
    return (
        f"✨ <b>{u.name or 'Без имени'}</b>, {u.age or '—'}\n"
        f"📍 {u.city or '—'}\n"
        f"👤 {username}\n\n"
        f"{u.bio or '—'}"
    )


@r.message(F.text == "💞 Совпадения")
async def matches_menu_improved(m: Message, db):
    async with db.session() as s:
        me = await get_user(s, m.from_user.id)
        if not me:
            return await m.answer("Сначала отправьте /start")
        rows = (
            await s.execute(
                select(Match)
                .where(or_(Match.user_a_id == me.id, Match.user_b_id == me.id))
                .order_by(Match.id.desc())
                .limit(20)
            )
        ).scalars().all()
        users = []
        for row in rows:
            uid = row.user_b_id if row.user_a_id == me.id else row.user_a_id
            user = await s.get(User, uid)
            if user and not user.is_banned and not user.deleted_at:
                users.append(user)

    if not users:
        return await m.answer("💞 Совпадений пока нет.", reply_markup=matches_actions())

    await m.answer("💞 <b>Ваши совпадения</b>\n\nЗдесь уже можно открыть Telegram, отправить приветствие или начать переписку через бота.")
    for user in users:
        await m.answer(
            profile_text(user),
            reply_markup=match_profile(user.tg_id, user.username),
        )
