from aiogram import Router,F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State,StatesGroup
from aiogram.types import CallbackQuery,Message,InlineKeyboardMarkup,InlineKeyboardButton
from .db import User
from .services import get_user
r=Router()
class SecretState(StatesGroup): text=State()
def actions(sender_tg,target_tg):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💞 Ответить",callback_data=f"secret:reply:{sender_tg}:{target_tg}")],[InlineKeyboardButton(text="👀 Раскрыть автора",callback_data=f"secret:reveal:{sender_tg}:{target_tg}")]])
@r.callback_query(F.data.startswith("secret:send:"))
async def start(c,state):
    target=int(c.data.split(":")[2]); await state.update_data(secret_target=target); await state.set_state(SecretState.text); await c.message.answer("💌 Напиши короткое тайное послание. Имя отправителя не будет показано."); await c.answer()
@r.message(SecretState.text)
async def send(m,state,db):
    text=(m.text or "").strip()
    if not 2<=len(text)<=500:return await m.answer("2–500 символов.")
    data=await state.get_data(); target_id=int(data["secret_target"])
    async with db.session() as s:
        sender=await get_user(s,m.from_user.id); target=await s.get(User,target_id)
        if not sender or not target or target.is_banned or target.deleted_at:return await m.answer("Получатель недоступен.")
        target_tg=target.tg_id
    await state.clear()
    await m.bot.send_message(target_tg,f"💌 <b>Тайное послание из Орбиты</b>\n\n{text}\n\nАвтор скрыт. Ты можешь ответить или раскрыть автора.",reply_markup=actions(sender.tg_id,target_tg))
    await m.answer("💌 Послание отправлено. Никаких публичных имён — только твой сигнал.")
@r.callback_query(F.data.startswith("secret:reveal:"))
async def reveal(c,db):
    _,_,sender_tg,target_tg=c.data.split(":")
    if int(target_tg)!=c.from_user.id:return await c.answer("Это послание не для тебя.",show_alert=True)
    async with db.session() as s: sender=await get_user(s,int(sender_tg))
    if not sender:return await c.answer("Автор недоступен.",show_alert=True)
    await c.message.answer(f"👀 Автор послания: <b>{sender.name}</b>"+(f"\n@{sender.username}" if sender.username else "")); await c.answer()
@r.callback_query(F.data.startswith("secret:reply:"))
async def reply(c,db):
    _,_,sender_tg,target_tg=c.data.split(":")
    if int(target_tg)!=c.from_user.id:return await c.answer("Это послание не для тебя.",show_alert=True)
    async with db.session() as s: sender=await get_user(s,int(sender_tg))
    if not sender:return await c.answer("Автор недоступен.",show_alert=True)
    await c.message.answer("💞 Если хочется продолжить — открой автора и используй обычный чат.")
    await c.answer()
