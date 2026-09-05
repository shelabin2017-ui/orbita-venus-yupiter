import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from .config import load_config
from .db import DB
from .handlers import r
from .features import r as features_router, photo_worker
from .keyboards import set_current_user_is_admin
from .redis_store import make_redis, make_fsm_storage

async def main():
    cfg = load_config()
    db = DB(cfg.database_url)
    redis = make_redis(cfg.redis_url)
    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=make_fsm_storage(redis))

    async def inject(handler, event, data):
        user = getattr(event, "from_user", None)
        set_current_user_is_admin(bool(user and user.id in cfg.admin_ids))
        data.update(db=db, config=cfg, redis=redis)
        return await handler(event, data)

    dp.message.middleware(inject)
    dp.callback_query.middleware(inject)
    dp.pre_checkout_query.middleware(inject)
    dp.include_router(features_router)
    dp.include_router(r)

    moderation_task = asyncio.create_task(photo_worker(bot, db, cfg))
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("🟢 Орбита запущена в режиме long polling")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        moderation_task.cancel()
        await asyncio.gather(moderation_task, return_exceptions=True)
        await bot.session.close()
        await redis.aclose()
        await db.engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
