import asyncio
import base64
import io
import json
import random
from datetime import datetime
from urllib.parse import quote

import httpx
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, or_

from .config import Config
from .db import User, Photo, StarTransaction, AuditLog, Match, Reaction
from .keyboards import admin, admin_back, main, match_profile, chat_cancel
from .services import get_user, is_vip, react
from .anti_spam import AntiSpam

r = Router()

class StarsState(StatesGroup):
    amount = State()
    reason = State()

class GameState(StatesGroup):
    answer = State()

class ChatState(StatesGroup):
    active = State()


def is_admin(uid: int, config: Config) -> bool:
    return uid in config.admin_ids

async def audit(s, admin_id, action, target_id=None, details=None):
    s.add(AuditLog(admin_tg_id=admin_id, action=action, target_id=target_id, details=details))

async def change_stars(s, user: User, amount: int, kind: str, reason: str | None, admin_tg_id: int | None = None):
    if amount == 0:
        raise ValueError("amount must not be zero")
    new_balance = user.stars_balance + amount
    if new_balance < 0:
        raise ValueError("insufficient balance")
    user.stars_balance = new_balance
    s.add(StarTransaction(user_id=user.id, amount=amount, balance_after=new_balance, kind=kind, reason=reason, admin_tg_id=admin_tg_id))
    return new_balance

async def moderate_photo(bot: Bot, photo: Photo, config: Config):
    if not config.photo_moderation_enabled or not config.photo_moderation_api_key:
        return None
    try:
        tg_file = await bot.get_file(photo.file_id)
        buf = io.BytesIO()
        await bot.download_file(tg_file.file_path, destination=buf)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        data_url = f"data:image/jpeg;base64,{encoded}"
        payload = {
            "model": config.photo_moderation_model,
            "input": [{"role": "user", "content": [
                {"type": "input_text", "text": "Moderate this dating-profile photo. Return ONLY JSON: {\"decision\":\"approve|reject|review\",\"score\":0-1,\"reason\":\"short reason\"}. Reject nudity/explicit sexual content, sexual services, graphic violence, hate/extremist propaganda, obvious scams or prohibited illegal content. Approve ordinary adult profile photos. Use review when uncertain."},
                {"type": "input_image", "image_url": data_url},
            ]}],
            "max_output_tokens": 120,
        }
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {config.photo_moderation_api_key}", "Content-Type": "application/json"}, json=payload)
            resp.raise_for_status()
            body = resp.json()
        text_parts = []
        for item in body.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    text_parts.append(content["text"])
        raw = "".join(text_parts).strip().strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
        result = json.loads(raw)
        decision = result.get("decision")
        if decision not in {"approve", "reject", "review"}:
            return None
        score = float(result.get("score", 0))
        return decision, max(0.0, min(1.0, score)), str(result.get("reason", ""))[:500]
    except Exception:
        return None

async def photo_worker(bot: Bot, db, config: Config):
    while True:
        try:
            if config.photo_moderation_enabled and config.photo_moderation_api_key:
                async with db.session() as s:
                    p = (await s.execute(select(Photo).where(Photo.moderation_status == "pending").order_by(Photo.id).limit(1))).scalar_one_or_none()
                    if p:
                        p.moderation_status = "processing"
                        await s.commit()
                        photo_id = p.id
                    else:
                        photo_id = None
                if photo_id is not None:
                    target = None
                    text = None
                    async with db.session() as s:
                        p = await s.get(Photo, photo_id)
                        result = await moderate_photo(bot, p, config) if p else None
                        if not p:
                            continue
                        if result is None:
                            p.moderation_status = "pending"
                        else:
                            decision, score, reason = result
                            p.moderation_status = {"approve": "approved", "reject": "rejected", "review": "pending"}[decision]
                            p.moderation_score = score
                            p.moderation_reason = reason
                            p.moderation_source = "auto" if decision != "review" else "ai_review"
                            p.moderated_at = datetime.utcnow()
                            user = await s.get(User, p.user_id)
                            if user and decision in {"approve", "reject"}:
                                target = user.tg_id
                                text = "📷 Фото автоматически одобрено." if decision == "approve" else "📷 Фото автоматически отклонено. Можно загрузить другое фото."
                        await s.commit()
                    if target and text:
                        try:
                            await bot.send_message(target, text)
                        except Exception:
                            pass
                    continue
            await asyncio.sleep(max(2, config.photo_moderation_poll_seconds))
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(max(2, config.photo_moderation_poll_seconds))

@r.message(F.text == "🛡 Админ-панель")
async def admin_panel_button(m: Message, config: Config):
    if not is_admin(m.from_user.id, config):
        return
    await m.answer("🛡 <b>АДМИН-ПАНЕЛЬ</b>\n\nВыберите раздел:", reply_markup=admin())

@r.callback_query(F.data == "adm:stars")
async def admin_stars_root(c: CallbackQuery, config: Config):
    if not is_admin(c.from_user.id, config):
        return await c.answer()
    await c.message.edit_text("⭐ <b>Stars</b>\n\nОткройте пользователя через «👥 Пользователи» → поиск. В карточке пользователя доступны начисление/списание и история Stars.", reply_markup=admin())
    await c.answer()

@r.callback_query(F.data.startswith("adm:stars:"))
async def admin_stars_menu(c: CallbackQuery, db, config: Config, state: FSMContext):
    if not is_admin(c.from_user.id, config):
        return await c.answer()
    uid = int(c.data.split(":")[2])
    async with db.session() as s:
        u = await s.get(User, uid)
        if not u:
            return await c.answer("Пользователь не найден", show_alert=True)
        balance = u.stars_balance
    await state.update_data(target_user_id=uid)
    await state.set_state(StarsState.amount)
    await c.message.answer(f"⭐ Баланс: <b>{balance}</b>\nВведите число Stars для начисления/списания. Например: <code>100</code> или <code>-50</code>.")
    await c.answer()

@r.message(StarsState.amount)
async def admin_stars_amount(m: Message, state: FSMContext, config: Config):
    if not is_admin(m.from_user.id, config):
        return
    try:
        amount = int((m.text or "").strip())
    except ValueError:
        return await m.answer("Введите целое число, например 100 или -50.")
    if amount == 0 or abs(amount) > 1_000_000:
        return await m.answer("Сумма должна быть от -1 000 000 до 1 000 000 и не равна нулю.")
    await state.update_data(amount=amount)
    await state.set_state(StarsState.reason)
    await m.answer("Причина операции? Напишите коротко или отправьте «без причины».")

@r.message(StarsState.reason)
async def admin_stars_reason(m: Message, state: FSMContext, db, config: Config):
    if not is_admin(m.from_user.id, config):
        return
    data = await state.get_data()
    reason = (m.text or "").strip()
    if reason.lower() == "без причины":
        reason = None
    async with db.session() as s:
        u = await s.get(User, int(data["target_user_id"]))
        if not u:
            await state.clear()
            return await m.answer("Пользователь не найден.", reply_markup=admin())
        try:
            balance = await change_stars(s, u, int(data["amount"]), "admin_adjustment", reason, m.from_user.id)
        except ValueError:
            await state.clear()
            return await m.answer("❌ Нельзя списать больше Stars, чем есть на балансе.", reply_markup=admin())
        await audit(s, m.from_user.id, "stars_adjustment", u.id, f"amount={data['amount']}; reason={reason or ''}; balance={balance}")
        tg_id = u.tg_id
        await s.commit()
    await state.clear()
    sign = "+" if int(data["amount"]) > 0 else ""
    try:
        await m.bot.send_message(tg_id, f"⭐ Баланс Stars изменён: <b>{sign}{data['amount']}</b>\nТекущий баланс: <b>{balance}</b>")
    except Exception:
        pass
    await m.answer(f"✅ Готово. Новый баланс: <b>{balance} Stars</b>.", reply_markup=admin())

@r.callback_query(F.data.startswith("adm:stars_history:"))
async def admin_stars_history(c: CallbackQuery, db, config: Config):
    if not is_admin(c.from_user.id, config):
        return await c.answer()
    uid = int(c.data.split(":")[2])
    async with db.session() as s:
        u = await s.get(User, uid)
        rows = (await s.execute(select(StarTransaction).where(StarTransaction.user_id == uid).order_by(StarTransaction.id.desc()).limit(10))).scalars().all()
    if not u:
        return await c.answer("Пользователь не найден", show_alert=True)
    lines = [f"⭐ <b>Stars пользователя</b>\nБаланс: <b>{u.stars_balance}</b>"]
    lines += [f"{'+' if x.amount > 0 else ''}{x.amount} → {x.balance_after} • {x.kind} • {x.reason or '—'}" for x in rows]
    await c.message.answer("\n".join(lines), reply_markup=admin())
    await c.answer()

@r.message(F.text == "⭐ Stars")
async def stars_balance(m: Message, db):
    async with db.session() as s:
        u = await get_user(s, m.from_user.id)
    if not u:
        return await m.answer("Сначала отправьте /start")
    await m.answer(f"⭐ Ваш баланс: <b>{u.stars_balance}</b> Stars")

@r.message(F.text == "🎮 Игры")
async def game_start(m: Message, state: FSMContext):
    a, b = random.randint(2, 20), random.randint(2, 20)
    op = random.choice(["+", "-"])
    answer = a + b if op == "+" else a - b
    await state.update_data(game_answer=answer)
    await state.set_state(GameState.answer)
    await m.answer(f"🎮 <b>Быстрая математика</b>\nСколько будет <b>{a} {op} {b}</b>?\n\nПравильный ответ принесёт <b>5 Stars</b>.")

@r.message(GameState.answer)
async def game_answer(m: Message, state: FSMContext, db):
    data = await state.get_data()
    try:
        answer = int((m.text or "").strip())
    except ValueError:
        return await m.answer("Введите число.")
    await state.clear()
    if answer != data.get("game_answer"):
        return await m.answer("❌ Неверно. Попробуйте ещё раз через кнопку 🎮 Игры.")
    async with db.session() as s:
        u = await get_user(s, m.from_user.id)
        if not u:
            return await m.answer("Сначала отправьте /start")
        balance = await change_stars(s, u, 5, "game_reward", "быстрая математика")
        await s.commit()
    await m.answer(f"🎉 Верно! +5 Stars. Ваш баланс: <b>{balance}</b>")

async def _is_match(s, a_id: int, b_id: int) -> bool:
    return (await s.execute(select(Match).where(
        or_(
            (Match.user_a_id == a_id) & (Match.user_b_id == b_id),
            (Match.user_a_id == b_id) & (Match.user_b_id == a_id),
        )
    ))).scalar_one_or_none() is not None

@r.callback_query(F.data.startswith(("like:", "skip:")))
async def improved_reaction(c: CallbackQuery, db, config, redis):
    act, uid = c.data.split(":")
    from .services import get_user, is_vip, react
    if not await AntiSpam(redis, config.antispam_seconds).allowed(c.from_user.id, "reaction"):
        return await c.answer("Слишком быстро. Попробуйте через секунду.", show_alert=True)
    async with db.session() as s:
        me = await get_user(s, c.from_user.id)
        other = await s.get(User, int(uid))
        if not me or not other or me.id == other.id or me.is_banned or me.deleted_at or not me.is_active or other.is_banned or other.deleted_at or not other.is_active:
            return await c.answer("Анкета недоступна.", show_alert=True)
        if act == "like":
            existing = (await s.execute(select(Reaction).where(Reaction.from_user_id == me.id, Reaction.to_user_id == other.id))).scalar_one_or_none()
            if not existing or existing.kind != "like":
                limit = config.vip_daily_likes if await is_vip(me) else config.free_daily_likes
                if not await AntiSpam(redis, config.antispam_seconds).daily_limit(me.tg_id, limit):
                    return await c.answer("Лимит лайков на сегодня. ⭐ VIP даёт повышенный лимит.", show_alert=True)
        matched = await react(s, me, other, "like" if act == "like" else "skip")
        await c.answer("❤️" if act == "like" else "👎")
        if matched:
            me_username = f"@{me.username}" if me.username else "Username не указан"
            other_username = f"@{other.username}" if other.username else "Username не указан"
            greeting = "Привет, я с Орбиты Венеры-Юпитера! 🌌"
            await c.message.answer(
                f"💞 <b>Взаимная симпатия!</b>\n\nТы понравился(ась) пользователю <b>{other.name}</b>.\n{other_username}\n\nНажми кнопку ниже, чтобы открыть Telegram-профиль или начать переписку.",
                reply_markup=match_profile(other.tg_id, other.username),
            )
            try:
                await c.bot.send_message(
                    other.tg_id,
                    f"💞 <b>Взаимная симпатия!</b>\n\nТы понравился(ась) пользователю <b>{me.name}</b>.\n{me_username}\n\n{greeting}",
                    reply_markup=match_profile(me.tg_id, me.username),
                )
            except Exception:
                pass
        from .handlers import show_next
        await show_next(c.message, s, me)

@r.callback_query(F.data.startswith("match:greet:"))
async def match_greet(c: CallbackQuery, db):
    uid = int(c.data.split(":")[2])
    greeting = "Привет, я с Орбиты Венеры-Юпитера! 🌌"
    async with db.session() as s:
        me = await get_user(s, c.from_user.id)
        other = await s.get(User, uid)
        if not me or not other or not await _is_match(s, me.id, other.id):
            return await c.answer("Эта функция доступна после взаимной симпатии.", show_alert=True)
    try:
        await c.bot.send_message(other.tg_id, f"👋 {greeting}\n\nСообщение от <b>{me.name}</b>.")
    except Exception:
        return await c.answer("Не удалось отправить приветствие.", show_alert=True)
    await c.answer("Приветствие отправлено!", show_alert=True)

@r.callback_query(F.data.startswith("chat:start:"))
async def chat_start(c: CallbackQuery, state: FSMContext, db):
    uid = int(c.data.split(":")[2])
    async with db.session() as s:
        me = await get_user(s, c.from_user.id)
        other = await s.get(User, uid)
        if not me or not other or not await _is_match(s, me.id, other.id):
            return await c.answer("Написать через бота можно после взаимной симпатии.", show_alert=True)
    await state.update_data(chat_target_id=uid)
    await state.set_state(ChatState.active)
    await c.message.answer("💬 Напишите сообщение, пришлите фото, голосовое, видео или другой поддерживаемый Telegram-контент. Я передам его вашему совпадению.", reply_markup=chat_cancel())
    await c.answer()

@r.callback_query(F.data == "chat:cancel")
async def chat_cancel_handler(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.answer("Диалог через бота завершён.", reply_markup=main())
    await c.answer()

@r.message(ChatState.active)
async def chat_relay(m: Message, state: FSMContext, db):
    data = await state.get_data()
    uid = data.get("chat_target_id")
    if not uid:
        await state.clear()
        return await m.answer("Диалог завершён.", reply_markup=main())
    async with db.session() as s:
        me = await get_user(s, m.from_user.id)
        other = await s.get(User, int(uid))
        valid = bool(me and other and not me.is_banned and not other.is_banned and not me.deleted_at and not other.deleted_at and await _is_match(s, me.id, other.id))
    if not valid:
        await state.clear()
        return await m.answer("Диалог недоступен.", reply_markup=main())
    try:
        await m.bot.send_message(other.tg_id, f"💌 Сообщение от <b>{me.name}</b>{f' (@{me.username})' if me.username else ''}:")
        await m.copy_to(other.tg_id)
        await m.answer("✅ Отправлено.")
    except Exception:
        await m.answer("Не удалось доставить сообщение. Попробуйте ещё раз.")
