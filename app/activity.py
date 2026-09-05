import asyncio
from datetime import datetime, timedelta
from aiogram import Bot
from sqlalchemy import select, func
from .db import User, Reaction


def _stage_for(days_inactive: int, reminder_days: int) -> int:
    if days_inactive >= max(reminder_days, 1):
        return 1
    return 0


async def touch_activity(db, redis, tg_id: int, interval_seconds: int = 900):
    """Record meaningful Telegram activity without writing to PostgreSQL on every update."""
    key = f"activity_touch:{tg_id}"
    try:
        if await redis.exists(key):
            return
        await redis.set(key, "1", ex=max(interval_seconds, 1))
    except Exception:
        # Activity tracking must never break the bot if Redis is temporarily unavailable.
        pass

    async with db.session() as s:
        user = (await s.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
        if not user:
            return
        now = datetime.utcnow()
        user.last_active_at = now
        user.last_inactive_reminder_at = None
        user.inactive_reminder_stage = 0
        await s.commit()


async def inactivity_worker(bot: Bot, db, config):
    """Send one useful re-engagement notice after prolonged inactivity."""
    interval = max(config.activity_worker_seconds, 60)
    while True:
        try:
            now = datetime.utcnow()
            cutoff = now - timedelta(days=max(config.inactivity_reminder_days, 1))
            async with db.session() as s:
                users = (await s.execute(
                    select(User).where(
                        User.is_banned == False,
                        User.deleted_at == None,
                        User.tg_id.is_not(None),
                        User.last_active_at.is_not(None),
                        User.last_active_at <= cutoff,
                        User.inactive_reminder_stage == 0,
                    ).limit(200)
                )).scalars().all()

                for user in users:
                    likes = await s.scalar(
                        select(func.count()).select_from(Reaction).where(
                            Reaction.to_user_id == user.id,
                            Reaction.kind == "like",
                            Reaction.created_at > user.last_active_at,
                        )
                    )
                    if likes:
                        text = (
                            f"🌌 Пока вас не было, ваша орбита получила {likes} "
                            f"{('симпатию' if likes == 1 else 'симпатии')}.\n"
                            "Загляните — возможно, там уже ждёт взаимная встреча."
                        )
                    else:
                        text = "🌙 Ваша орбита давно не активна. Загляните, если хотите продолжить поиск."

                    try:
                        await bot.send_message(user.tg_id, text)
                        user.last_inactive_reminder_at = now
                        user.inactive_reminder_stage = 1
                    except Exception:
                        # User may have blocked/deleted the bot; do not retry every worker cycle.
                        user.last_inactive_reminder_at = now
                        user.inactive_reminder_stage = 1
                if users:
                    await s.commit()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"⚠️ inactivity_worker: {exc}")
        await asyncio.sleep(interval)
