import random
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, or_, func
from .db import User, Reaction, Match, BlindDate
from .config import Config
from .services import get_user, distance_km

r = Router()
QUESTIONS = [
    "Если бы завтра можно было улететь в любую точку мира — куда?",
    "Какой маленький поступок моментально располагает тебя к человеку?",
    "Идеальное первое свидание: прогулка, кофе, приключение или что-то своё?",
    "Какой трек описывает твоё настроение сегодня?",
    "Что ты умеешь делать так, что друзья всегда просят тебя об этом?",
    "Какой спонтанный поступок ты давно хочешь совершить?",
]
class QuestionState(StatesGroup): answer = State()
class InterestState(StatesGroup): value = State()
class WorkshopState(StatesGroup): bio = State()

def universe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💫 Совместимость", callback_data="uni:compat"), InlineKeyboardButton(text="❓ Вопрос дня", callback_data="uni:question")],
        [InlineKeyboardButton(text="🙈 Свидание вслепую", callback_data="uni:blind"), InlineKeyboardButton(text="🏆 Достижения", callback_data="uni:achievements")],
        [InlineKeyboardButton(text="🛠 Мастерская Леонардо", callback_data="uni:workshop"), InlineKeyboardButton(text="🧪 Экспедиции", callback_data="uni:expeditions")],
        [InlineKeyboardButton(text="🎯 Мои интересы", callback_data="uni:interests"), InlineKeyboardButton(text="📡 Орбита недели", callback_data="uni:week")],
    ])
def blind_keyboard(pair_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✨ Хочу продолжить", callback_data=f"blind:interest:{pair_id}")],[InlineKeyboardButton(text="👀 Открыть после взаимного интереса", callback_data=f"blind:reveal:{pair_id}")]])
def tokens(text): return {x.strip(".,!?;:()[]{}\n\t").lower() for x in (text or "").split() if len(x.strip(".,!?;:()[]{}")) >= 3}
def compatibility(me, other):
    score=45; reasons=[]
    if me.city and other.city and me.city.strip().lower()==other.city.strip().lower(): score+=15; reasons.append("один город")
    if me.age and other.age:
        diff=abs(me.age-other.age); score+=max(0,15-diff*2)
        if diff<=3: reasons.append("близкий возраст")
    if me.looking_for in ("any",None) or me.looking_for==other.gender: score+=10
    overlap=tokens(me.interests)&tokens(other.interests)
    if overlap: score+=min(20,len(overlap)*5); reasons.append("общие интересы")
    if me.bio and other.bio:
        if tokens(me.bio)&tokens(other.bio): score+=min(10,len(tokens(me.bio)&tokens(other.bio))*2); reasons.append("похожий вайб")
    if me.latitude is not None and other.latitude is not None:
        d=distance_km(me.latitude,me.longitude,other.latitude,other.longitude); score+=10 if d<=10 else 5 if d<=30 else 0
        if d<=30: reasons.append("недалеко друг от друга")
    return min(99,max(1,score)),reasons
async def send_compatibility(message,s,me,other):
    score,reasons=compatibility(me,other)
    await message.answer(f"💫 <b>Орбитальная совместимость — {score}%</b>\n\n✨ {other.name}, {other.age}\n📍 {other.city or '—'}\n\n" + ("Похоже на: "+", ".join(reasons[:4])+"." if reasons else "Пока мало данных — но это можно исправить."))

@r.message(F.text == "🌌 Моя Вселенная")
async def universe_menu(m): await m.answer("🌌 <b>Твоя маленькая вселенная знакомств</b>\n\nНе только лайки: совместимость, эксперименты, игры и случайные открытия.",reply_markup=universe_keyboard())
@r.callback_query(F.data == "uni:question")
async def daily_question(c,db,state):
    today=datetime.utcnow().date()
    async with db.session() as s:
        me=await get_user(s,c.from_user.id)
        if not me: return await c.answer("Сначала /start",show_alert=True)
        q=QUESTIONS[datetime.utcnow().timetuple().tm_yday%len(QUESTIONS)]
        if me.daily_question_date and me.daily_question_date.date()==today and me.daily_question_answer:
            return await c.message.answer(f"❓ <b>Вопрос дня</b>\n\n{q}\n\nТвой ответ:\n<i>{me.daily_question_answer}</i>")
    await state.set_state(QuestionState.answer); await c.message.answer(f"❓ <b>Вопрос дня</b>\n\n{q}\n\nОтветь обычным сообщением — он появится в твоей анкете сегодня."); await c.answer()
@r.message(QuestionState.answer)
async def save_daily_answer(m,state,db):
    value=(m.text or "").strip()
    if len(value)<2 or len(value)>300: return await m.answer("Ответ должен быть от 2 до 300 символов.")
    async with db.session() as s:
        me=await get_user(s,m.from_user.id)
        if me: me.daily_question_answer=value; me.daily_question_date=datetime.utcnow(); await s.commit()
    await state.clear(); await m.answer("🌟 Ответ сохранён. Он будет частью твоей анкеты сегодня.")
@r.callback_query(F.data == "uni:interests")
async def interests_start(c,state,db):
    async with db.session() as s: me=await get_user(s,c.from_user.id)
    await state.set_state(InterestState.value); await c.message.answer(f"🎯 Напиши интересы через запятую.\nНапример: музыка, путешествия, кино, спорт.\n\nСейчас: {me.interests or 'не указаны'}"); await c.answer()
@r.message(InterestState.value)
async def interests_save(m,state,db):
    value=(m.text or "").strip()
    if not 2<=len(value)<=300: return await m.answer("2–300 символов.")
    async with db.session() as s:
        me=await get_user(s,m.from_user.id)
        if me: me.interests=value; await s.commit()
    await state.clear(); await m.answer("🎯 Интересы сохранены. Теперь совместимость станет точнее.",reply_markup=universe_keyboard())
@r.callback_query(F.data == "uni:compat")
async def compat(c,db):
    async with db.session() as s:
        me=await get_user(s,c.from_user.id)
        if not me: return await c.answer("Сначала /start",show_alert=True)
        seen=select(Reaction.to_user_id).where(Reaction.from_user_id==me.id)
        candidates=(await s.execute(select(User).where(User.id!=me.id,User.is_active.is_(True),User.is_banned.is_(False),User.deleted_at.is_(None),User.moderation_status=="approved",~User.id.in_(seen)).limit(80))).scalars().all()
        ranked=sorted(((compatibility(me,u)[0],u) for u in candidates),key=lambda x:x[0],reverse=True)[:3]
    if not ranked: return await c.message.answer("💫 Пока некого сравнивать — загляни в «Смотреть» позже.")
    await c.message.answer("💫 <b>Три самые перспективные орбиты</b>")
    for score,u in ranked: await c.message.answer(f"<b>{score}%</b> — {u.name}, {u.age}\n📍 {u.city or '—'}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💫 Почему мы совместимы",callback_data=f"compat:{u.id}")]]))
    await c.answer()
@r.callback_query(F.data.startswith("compat:"))
async def compat_detail(c,db):
    async with db.session() as s:
        me=await get_user(s,c.from_user.id); other=await s.get(User,int(c.data.split(":")[1]))
        if me and other: await send_compatibility(c.message,s,me,other)
    await c.answer()
@r.callback_query(F.data == "uni:blind")
async def blind_join(c,db,redis):
    key=f"blind_wait:{c.from_user.id}"
    if await redis.get(key): return await c.answer("Ты уже в поиске пары. Подожди немного.",show_alert=True)
    async with db.session() as s:
        me=await get_user(s,c.from_user.id)
        if not me: return await c.answer("Сначала /start",show_alert=True)
        other_tg=await redis.get("blind_wait_any")
        if other_tg:
            other=await get_user(s,int(other_tg))
            if other and other.id!=me.id and other.is_active and not other.is_banned and not other.deleted_at:
                a,b=sorted((me.id,other.id)); pair=(await s.execute(select(BlindDate).where(BlindDate.user_a_id==a,BlindDate.user_b_id==b))).scalar_one_or_none()
                if not pair: pair=BlindDate(user_a_id=a,user_b_id=b,status="paired"); s.add(pair); await s.commit()
                await redis.delete("blind_wait_any"); await redis.delete(f"blind_wait:{other.tg_id}")
                text=f"🙈 <b>Свидание вслепую найдено!</b>\n\nТвой собеседник: <b>Орбита #{pair.id}</b>\n\n1. Идеальный вечер?\n2. Куда бы ты поехал(а) завтра?\n3. Что тебя смешит почти всегда?"
                await c.message.answer(text,reply_markup=blind_keyboard(pair.id))
                try: await c.bot.send_message(other.tg_id,text,reply_markup=blind_keyboard(pair.id))
                except Exception: pass
                return await c.answer("Пара найдена ✨")
        await redis.setex("blind_wait_any",600,str(me.tg_id)); await redis.setex(key,600,"1")
    await c.message.answer("🙈 Ты в очереди на свидание вслепую. Я соединю тебя с первым участником в ближайшие 10 минут."); await c.answer()
@r.callback_query(F.data.startswith("blind:interest:"))
async def blind_interest(c,db,redis):
    pair_id=int(c.data.split(":")[2])
    async with db.session() as s:
        pair=await s.get(BlindDate,pair_id); me=await get_user(s,c.from_user.id)
        if not pair or not me or me.id not in {pair.user_a_id,pair.user_b_id}: return await c.answer("Свидание не найдено",show_alert=True)
        other=await s.get(User,pair.user_b_id if pair.user_a_id==me.id else pair.user_a_id)
    await redis.setex(f"blind_interest:{pair_id}:{me.id}",86400,"1"); await c.answer("Сигнал отправлен ✨")
    if other:
        try: await c.bot.send_message(other.tg_id,"✨ Твой собеседник хочет продолжить общение. Если чувство взаимно — нажми «Хочу продолжить».",reply_markup=blind_keyboard(pair_id))
        except Exception: pass
@r.callback_query(F.data.startswith("blind:reveal:"))
async def blind_reveal(c,db,redis):
    pair_id=int(c.data.split(":")[2])
    async with db.session() as s:
        pair=await s.get(BlindDate,pair_id); me=await get_user(s,c.from_user.id)
        if not pair or not me or me.id not in {pair.user_a_id,pair.user_b_id}: return await c.answer("Не найдено",show_alert=True)
        other_id=pair.user_b_id if pair.user_a_id==me.id else pair.user_a_id
        a=await redis.get(f"blind_interest:{pair_id}:{me.id}"); b=await redis.get(f"blind_interest:{pair_id}:{other_id}")
        if not(a and b): return await c.answer("Нужно взаимное желание продолжить ✨",show_alert=True)
        pair.status="revealed"; pair.revealed_at=datetime.utcnow(); other=await s.get(User,other_id); await s.commit()
    await c.message.answer(f"👀 <b>Орбиты раскрыты!</b>\n\n{other.name}, {other.age}\n📍 {other.city or '—'}")
    try: await c.bot.send_message(other.tg_id,f"👀 <b>Орбиты раскрыты!</b>\n\n{me.name}, {me.age}\n📍 {me.city or '—'}")
    except Exception: pass
    await c.answer("Раскрыто ✨")
@r.callback_query(F.data == "uni:achievements")
async def achievements(c,db):
    async with db.session() as s:
        me=await get_user(s,c.from_user.id)
        if not me: return await c.answer("Сначала /start",show_alert=True)
        likes=await s.scalar(select(func.count()).select_from(Reaction).where(Reaction.from_user_id==me.id,Reaction.kind.in_(["like","spark"])))
        matches=await s.scalar(select(func.count()).select_from(Match).where(or_(Match.user_a_id==me.id,Match.user_b_id==me.id)))
    badges=[]
    if likes>=1: badges.append("💫 Первый сигнал")
    if likes>=10: badges.append("🔥 Искатель искр")
    if matches>=1: badges.append("💞 Первая взаимность")
    if matches>=5: badges.append("🪐 Магнит орбит")
    if me.interests: badges.append("🎯 Исследователь интересов")
    if me.daily_question_answer: badges.append("❓ Голос дня")
    await c.message.answer("🏆 <b>Орбитальные достижения</b>\n\n"+("\n".join(badges) if badges else "Пока пусто. Начни исследование своей орбиты!")); await c.answer()
@r.callback_query(F.data == "uni:week")
async def orbit_week(c,db):
    since=datetime.utcnow()-timedelta(days=7)
    async with db.session() as s:
        me=await get_user(s,c.from_user.id)
        if not me: return await c.answer("Сначала /start",show_alert=True)
        likes=await s.scalar(select(func.count()).select_from(Reaction).where(Reaction.from_user_id==me.id,Reaction.kind.in_(["like","spark"]),Reaction.created_at>=since))
        matches=await s.scalar(select(func.count()).select_from(Match).where(or_(Match.user_a_id==me.id,Match.user_b_id==me.id),Match.created_at>=since))
    await c.message.answer(f"📡 <b>Орбита недели</b>\n\n❤️ Сигналов отправлено: <b>{likes}</b>\n💞 Новых совпадений: <b>{matches}</b>\n\nТолько твоя история — без рейтингов других людей."); await c.answer()
@r.callback_query(F.data == "uni:workshop")
async def workshop_start(c,state,db):
    async with db.session() as s: me=await get_user(s,c.from_user.id)
    await state.set_state(WorkshopState.bio); await c.message.answer(f"🛠 <b>Мастерская Леонардо</b>\n\nПришли текст «О себе», и я сделаю его живее, не выдумывая фактов.\n\nСейчас:\n{me.bio or 'пусто'}"); await c.answer()
@r.message(WorkshopState.bio)
async def workshop(m,state,db,config:Config):
    text=(m.text or "").strip()
    if not 2<=len(text)<=500: return await m.answer("2–500 символов.")
    result=text
    if config.photo_moderation_api_key:
        import httpx
        payload={"model":config.photo_moderation_model,"input":f"Rewrite this dating profile bio in Russian. Keep every factual detail, do not invent anything, make it warm, concise and natural. Return only the rewritten bio, max 500 chars.\n\n{text}","max_output_tokens":180}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp=await client.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {config.photo_moderation_api_key}","Content-Type":"application/json"},json=payload); resp.raise_for_status(); body=resp.json()
            parts=[content.get("text","") for item in body.get("output",[]) for content in item.get("content",[]) if content.get("type") in {"output_text","text"}]
            if parts: result="".join(parts).strip()[:500]
        except Exception: pass
    await state.clear(); await m.answer(f"✨ <b>Вариант Леонардо:</b>\n\n{result}\n\nСкопируй его в «✏️ Изменить» → «📝 О себе», если нравится.")
@r.callback_query(F.data == "uni:expeditions")
async def expeditions(c):
    week=datetime.utcnow().isocalendar().week
    themes=[("🌙 Ночная экспедиция","Что ты делаешь, когда никто не видит?"),("🎬 Экспедиция первого свидания","Выбери необычный сценарий первого свидания и найди единомышленника."),("🗺 Экспедиция случайных городов","Познакомься с человеком из другого города и обменяйтесь местами мечты."),("🎵 Музыкальная экспедиция","Отправь трек, который тебя описывает, и найди похожий ритм.")]
    title,desc=themes[week%len(themes)]; await c.message.answer(f"🧪 <b>{title}</b>\n\n{desc}\n\nЭкспедиции меняются каждую неделю — без рейтингов и гонки за очками."); await c.answer()
