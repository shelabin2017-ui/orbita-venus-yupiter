from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from .db import User, Reaction
from .services import get_user, is_vip, react
from .anti_spam import AntiSpam
r=Router()
@r.callback_query(F.data.startswith("spark:"))
async def spark(c: CallbackQuery, db, config, redis):
    if not await AntiSpam(redis, config.antispam_seconds).allowed(c.from_user.id,"spark"):
        return await c.answer("Слишком быстро. Попробуй через секунду.",show_alert=True)
    uid=int(c.data.split(":")[1])
    async with db.session() as s:
        me=await get_user(s,c.from_user.id); other=await s.get(User,uid)
        if not me or not other or me.id==other.id or other.is_banned or other.deleted_at or not other.is_active: return await c.answer("Анкета недоступна.",show_alert=True)
        limit=3 if await is_vip(me) else 1
        key=f"spark_daily:{me.tg_id}"
        used=int(await redis.get(key) or 0)
        if used>=limit: return await c.answer("🔥 Искры на сегодня закончились. VIP даёт больше искр.",show_alert=True)
        await redis.incr(key); await redis.expire(key,86400)
        matched=await react(s,me,other,"spark")
    await c.answer("🔥 Искра отправлена")
    await c.message.answer(f"🔥 Ты отправил(а) особый сигнал пользователю <b>{other.name}</b>. Это сильнее обычного лайка.")
    if matched:
        await c.message.answer("💞 <b>Искра взаимна!</b> Орбиты совпали.")
        try: await c.bot.send_message(other.tg_id,f"🔥 <b>У вас взаимная искра!</b> {me.name} отправил(а) тебе особый сигнал.")
        except Exception: pass
