import asyncio
from datetime import datetime,timedelta
from aiogram import Router,F
from aiogram.filters import CommandStart,Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State,StatesGroup
from aiogram.types import Message,CallbackQuery,LabeledPrice
from sqlalchemy import select,func,or_
from .db import User,Photo,Report,Payment,AuditLog,Block,Match,Reaction
from .config import Config
from .services import get_user,next_profile,public_photos,is_vip,like_count_today,react
from .keyboards import main,gender,profile,admin,moderate,vip,confirm_delete,edit_fields,report_reasons,matches_actions,user_actions,report_actions

r=Router()

class Reg(StatesGroup): name=State();age=State();gender=State();looking=State();city=State();location=State();bio=State()
class Edit(StatesGroup): field=State();value=State()

def ptxt(u): return f"✨ <b>{u.name}</b>, {u.age}\n📍 {u.city or '—'}\n\n{u.bio or '—'}"

async def send_profile(m,s,u):
    photos=await public_photos(s,u.id)
    if photos:
        await m.answer_media_group([__import__("aiogram").types.InputMediaPhoto(media=x.file_id,caption=ptxt(u) if i==0 else None) for i,x in enumerate(photos)])
        await m.answer("Выберите действие:",reply_markup=profile(u.id))
    else: await m.answer(ptxt(u),reply_markup=profile(u.id))

async def show_next(m,s,me,radius=None):
    u=await next_profile(s,me,radius)
    if not u: await m.answer("🌌 Подходящих анкет пока нет.",reply_markup=main());return
    await send_profile(m,s,u)

@r.message(CommandStart())
async def start(m:Message,state:FSMContext,db,config:Config):
    async with db.session() as s:
        u=await get_user(s,m.from_user.id)
        if not u:
            u=User(tg_id=m.from_user.id,username=m.from_user.username,name=m.from_user.first_name)
            s.add(u);await s.commit()
        if u.is_banned: await m.answer("Аккаунт заблокирован.");return
        if u.deleted_at:
            u.deleted_at=None;u.is_active=False;u.moderation_status="pending";await s.commit()
            await state.clear()
            await m.answer("♻️ Анкета восстановлена и отправлена на повторную модерацию.",reply_markup=main())
            return
        if not u.age:
            await state.set_state(Reg.name);await m.answer("🌠 Добро пожаловать! Как вас зовут?")
        else: await m.answer("С возвращением в Орбиту 💫",reply_markup=main())

@r.message(Reg.name)
async def name(m,state): 
    if not m.text or not 2<=len(m.text.strip())<=40:return await m.answer("Имя: 2–40 символов.")
    await state.update_data(name=m.text.strip());await state.set_state(Reg.age);await m.answer("Возраст (18–99)?")

@r.message(Reg.age)
async def age(m,state,config):
    try:a=int(m.text)
    except: return await m.answer("Введите число.")
    if not config.min_age<=a<=config.max_age:return await m.answer("Недопустимый возраст.")
    await state.update_data(age=a);await state.set_state(Reg.gender);await m.answer("Ваш пол:",reply_markup=gender("g"))

@r.callback_query(Reg.gender,F.data.startswith("g:"))
async def g(c,state): await state.update_data(gender=c.data.split(":")[1]);await state.set_state(Reg.looking);await c.message.edit_text("Кого ищете?",reply_markup=gender("l"));await c.answer()

@r.callback_query(Reg.looking,F.data.startswith("l:"))
async def l(c,state): await state.update_data(looking_for=c.data.split(":")[1]);await state.set_state(Reg.city);await c.message.edit_text("Ваш город?");await c.answer()

@r.message(Reg.city)
async def city(m,state):
    value=(m.text or "").strip()
    if not 2 <= len(value) <= 100:
        return await m.answer("Введите город (2–100 символов).")
    await state.update_data(city=value)
    await state.set_state(Reg.location)
    await m.answer("📍 Пришлите геолокацию через скрепку Telegram. Можно нажать «Пропустить».")

@r.message(Reg.location)
async def location(m,state):
    if m.location: await state.update_data(latitude=m.location.latitude,longitude=m.location.longitude)
    elif not (m.text and m.text.lower()=="пропустить"): return await m.answer("Пришлите геолокацию или «Пропустить».")
    await state.set_state(Reg.bio);await m.answer("Коротко о себе (2–500 символов).")

@r.message(Reg.bio)
async def bio(m,state,db):
    if not m.text or not 2<=len(m.text.strip())<=500:return await m.answer("2–500 символов.")
    d=await state.get_data()
    async with db.session() as s:
        u=await get_user(s,m.from_user.id)
        for k in ("name","age","gender","looking_for","city","latitude","longitude","bio"): setattr(u,k,d.get(k))
        u.moderation_status="pending";u.is_active=False;await s.commit()
    await state.clear();await m.answer("Анкета отправлена на модерацию. После одобрения вы появитесь в поиске.",reply_markup=main())

@r.message(F.text=="🔎 Смотреть")
async def browse(m,db):
    async with db.session() as s:
        u=await get_user(s,m.from_user.id)
        if not u or u.moderation_status!="approved":return await m.answer("Анкета должна быть одобрена модератором.")
        await show_next(m,s,u)

@r.message(F.text=="📍 Поиск рядом")
async def nearby(m,db):
    async with db.session() as s:
        u=await get_user(s,m.from_user.id)
        if not u or u.latitude is None:return await m.answer("Сначала добавьте геолокацию в анкете.")
        await m.answer("📍 Показываю анкеты в радиусе 25 км.")
        await show_next(m,s,u,25)

@r.callback_query(F.data.startswith(("like:","skip:")))
async def reaction(c,db,config,redis):
    act,uid=c.data.split(":")
    from .anti_spam import AntiSpam
    if not await AntiSpam(redis, config.antispam_seconds).allowed(c.from_user.id, "reaction"):
        return await c.answer("Слишком быстро. Попробуйте через секунду.", show_alert=True)
    async with db.session() as s:
        me=await get_user(s,c.from_user.id);other=await s.get(User,int(uid))
        if not me or not other or me.id==other.id or me.is_banned or me.deleted_at or not me.is_active or other.is_banned or other.deleted_at or not other.is_active:
            return await c.answer("Анкета недоступна.",show_alert=True)
        if act=="like":
            existing=(await s.execute(select(Reaction).where(Reaction.from_user_id==me.id,Reaction.to_user_id==other.id))).scalar_one_or_none()
            if not existing or existing.kind != "like":
                limit = config.vip_daily_likes if await is_vip(me) else config.free_daily_likes
                if not await AntiSpam(redis, config.antispam_seconds).daily_limit(me.tg_id, limit):
                    return await c.answer("Лимит лайков на сегодня. ⭐ VIP даёт повышенный лимит.", show_alert=True)
        matched=await react(s,me,other,"like" if act=="like" else "skip")
        await c.answer("❤️" if act=="like" else "👎")
        if matched:
            await c.message.answer(f"💞 Орбиты совпали! Вы понравились друг другу с {other.name}.")
            try: await c.bot.send_message(other.tg_id,f"💞 У вас взаимная симпатия с {me.name}!")
            except: pass
        await show_next(c.message,s,me)

@r.callback_query(F.data.startswith("block:"))
async def block(c,db):
    target_id=int(c.data.split(":")[1])
    async with db.session() as s:
        me=await get_user(s,c.from_user.id)
        other=await s.get(User,target_id)
        if not me or not other or me.id==other.id:
            return await c.answer("Не найдено",show_alert=True)
        exists=(await s.execute(select(Block).where(Block.blocker_id==me.id,Block.blocked_id==other.id))).scalar_one_or_none()
        if not exists: s.add(Block(blocker_id=me.id,blocked_id=other.id)); await s.commit()
    await c.answer("Заблокировано.");await c.message.answer("🚫 Пользователь скрыт.")

@r.callback_query(F.data.startswith("report:"))
async def report_start(c,db):
    uid=int(c.data.split(":")[1])
    async with db.session() as s:
        me=await get_user(s,c.from_user.id); other=await s.get(User,uid)
        if not me or not other or me.id==other.id: return await c.answer("Не найдено",show_alert=True)
    await c.message.answer("🚩 Выберите причину жалобы:",reply_markup=report_reasons(uid)); await c.answer()

@r.callback_query(F.data.startswith("report_reason:"))
async def report_reason(c,db):
    _,reason,uid=c.data.split(":")
    if reason=="cancel": return await c.message.edit_text("Жалоба отменена.")
    uid=int(uid)
    labels={"spam":"Спам","adult":"Контент 18+","scam":"Мошенничество","other":"Другое"}
    async with db.session() as s:
        me=await get_user(s,c.from_user.id); other=await s.get(User,uid)
        if not me or not other or me.id==other.id: return await c.answer("Не найдено",show_alert=True)
        s.add(Report(reporter_id=me.id,reported_id=other.id,reason=labels.get(reason,reason)))
        await s.commit()
    await c.message.edit_text("🚩 Жалоба отправлена модераторам. Спасибо."); await c.answer()

@r.message(F.text=="💞 Совпадения")
async def matches_menu(m,db):
    async with db.session() as s:
        me=await get_user(s,m.from_user.id)
        if not me: return await m.answer("Сначала отправьте /start")
        rows=(await s.execute(select(Match).where(or_(Match.user_a_id==me.id,Match.user_b_id==me.id)).order_by(Match.id.desc()).limit(20))).scalars().all()
        ids=[x.user_b_id if x.user_a_id==me.id else x.user_a_id for x in rows]
        users=[]
        for uid in ids:
            u=await s.get(User,uid)
            if u and not u.is_banned and not u.deleted_at: users.append(u)
    if not users: return await m.answer("💞 Совпадений пока нет.",reply_markup=matches_actions())
    await m.answer("💞 <b>Ваши совпадения</b>")
    for u in users: await m.answer(ptxt(u))

@r.callback_query(F.data=="match:menu")
async def match_menu_callback(c): await c.message.answer("Главное меню",reply_markup=main()); await c.answer()

@r.callback_query(F.data=="match:browse")
async def match_browse(c,db):
    async with db.session() as s:
        me=await get_user(s,c.from_user.id)
        if me: await show_next(c.message,s,me)
    await c.answer()

@r.message(F.text=="🗑 Удалить анкету")
async def delstart(m): await m.answer("Удалить анкету? Её можно будет восстановить через /start.",reply_markup=confirm_delete())

@r.callback_query(F.data.startswith("delete:"))
async def delete(c,db):
    if c.data.endswith(":no"):return await c.message.edit_text("Отмена.")
    async with db.session() as s:
        u=await get_user(s,c.from_user.id)
        if not u:
            return await c.answer("Анкета не найдена.",show_alert=True)
        u.deleted_at=datetime.utcnow();u.is_active=False;await s.commit()
    await c.message.edit_text("Анкета удалена. Для восстановления отправьте /start.");await c.answer()

@r.message(F.text=="👤 Моя анкета")
async def my_profile(m,db):
    async with db.session() as s:
        u=await get_user(s,m.from_user.id)
        if not u: return await m.answer("Сначала отправьте /start")
        photos=await public_photos(s,u.id)
        text=ptxt(u)+f"\n\n📷 Фото: {len(photos)}"
    if photos:
        from aiogram.types import InputMediaPhoto
        await m.answer_media_group([InputMediaPhoto(media=x.file_id,caption=text if i==0 else None) for i,x in enumerate(photos)])
    else:
        await m.answer(text)

@r.message(F.text=="✏️ Изменить")
async def edit_menu(m,db):
    async with db.session() as s:
        u=await get_user(s,m.from_user.id)
        if not u: return await m.answer("Сначала отправьте /start")
    await m.answer("Что изменить? Изменения анкеты снова уйдут на модерацию.",reply_markup=edit_fields())

@r.callback_query(F.data.startswith("edit:"))
async def edit_start(c,state):
    field=c.data.split(":",1)[1]
    if field=="cancel": return await c.message.edit_text("Отмена.")
    await state.update_data(field=field); await state.set_state(Edit.value)
    prompts={"name":"Новое имя (2–40):","age":"Новый возраст (18–99):","city":"Новый город:","bio":"Новое описание (2–500):","gender":"Выберите пол:","looking":"Выберите, кого ищете:"}
    if field=="gender": return await c.message.edit_text(prompts[field],reply_markup=gender("eg"))
    if field=="looking": return await c.message.edit_text(prompts[field],reply_markup=gender("el"))
    await c.message.edit_text(prompts[field]); await c.answer()

@r.callback_query(Edit.value,F.data.startswith("eg:"))
async def edit_gender(c,state,db): await edit_apply(c.from_user.id,"gender",c.data.split(":")[1],state,db,c.message); await c.answer()

@r.callback_query(Edit.value,F.data.startswith("el:"))
async def edit_looking(c,state,db): await edit_apply(c.from_user.id,"looking_for",c.data.split(":")[1],state,db,c.message); await c.answer()

async def edit_apply(tg_id,field,value,state,db,message):
    async with db.session() as s:
        u=await get_user(s,tg_id)
        if not u: return await message.answer("Пользователь не найден.")
        setattr(u,field,value); u.moderation_status="pending"; u.is_active=False; await s.commit()
    await state.clear(); await message.edit_text("Изменения отправлены на модерацию.")

@r.message(Edit.value)
async def edit_value(m,state,db,config):
    d=await state.get_data(); field=d.get("field"); value=(m.text or "").strip()
    if field=="age":
        try: value=int(value)
        except: return await m.answer("Введите число.")
        if not config.min_age<=value<=config.max_age: return await m.answer("Недопустимый возраст.")
    elif field=="name" and not 2<=len(value)<=40: return await m.answer("Имя: 2–40 символов.")
    elif field=="city" and not 2<=len(value)<=100: return await m.answer("Город: 2–100 символов.")
    elif field=="bio" and not 2<=len(value)<=500: return await m.answer("Описание: 2–500 символов.")
    async with db.session() as s:
        u=await get_user(s,m.from_user.id)
        if not u: return await m.answer("Не найдено.")
        setattr(u,field,value); u.moderation_status="pending"; u.is_active=False; await s.commit()
    await state.clear(); await m.answer("Изменения отправлены на модерацию.",reply_markup=main())

@r.message(Command("restore"))
async def restore(m,db):
    async with db.session() as s:
        u=await get_user(s,m.from_user.id)
        if not u: return await m.answer("Анкета не найдена. Отправьте /start.")
        if u.is_banned: return await m.answer("Аккаунт заблокирован.")
        if not u.deleted_at: return await m.answer("Анкета не удалена.")
        u.deleted_at=None; u.is_active=False; u.moderation_status="pending"; await s.commit()
    await m.answer("♻️ Анкета восстановлена и отправлена на повторную модерацию.",reply_markup=main())

@r.message(F.photo)
async def upload_photo(m,db,config):
    async with db.session() as s:
        u=await get_user(s,m.from_user.id)
        if not u or u.deleted_at or u.is_banned: return
        count=await s.scalar(select(func.count()).select_from(Photo).where(Photo.user_id==u.id,Photo.moderation_status!="rejected")) or 0
        if count>=config.max_photos: return await m.answer(f"Максимум {config.max_photos} фото.")
        max_pos=await s.scalar(select(func.coalesce(func.max(Photo.position),-1)).where(Photo.user_id==u.id))
        s.add(Photo(user_id=u.id,file_id=m.photo[-1].file_id,position=(max_pos or -1)+1,moderation_status="pending")); await s.commit()
    await m.answer("📷 Фото получено и отправлено на модерацию.")

@r.message(F.text=="⭐ VIP")
async def vip_menu(m,config): await m.answer(f"⭐ VIP\n\nБольше лайков, приоритет в выдаче и дополнительные возможности.\nЦена: {config.stars_vip_price} Stars.",reply_markup=vip(config.stars_vip_price))

@r.callback_query(F.data=="buy:vip")
async def buy(c,config):
    payload=f"vip:{c.from_user.id}:{int(datetime.utcnow().timestamp())}"
    await c.bot.send_invoice(c.from_user.id,"VIP «Орбита»","VIP на 30 дней",payload,"XTR",[LabeledPrice(label="VIP 30 дней",amount=config.stars_vip_price)])

@r.pre_checkout_query()
async def precheckout(q,config):
    ok=(q.currency=="XTR" and q.invoice_payload.startswith(f"vip:{q.from_user.id}:") and q.total_amount==config.stars_vip_price)
    await q.answer(ok=ok, error_message=None if ok else "Некорректный счёт VIP.")

@r.message(F.successful_payment)
async def payment(m,db,config):
    pay=m.successful_payment
    if pay.currency != "XTR" or not pay.invoice_payload.startswith(f"vip:{m.from_user.id}:"):
        return await m.answer("Платёж отклонён: некорректный счёт.")
    async with db.session() as s:
        u=await get_user(s,m.from_user.id)
        if not u: return await m.answer("Пользователь не найден. Отправьте /start.")
        if (await s.execute(select(Payment).where(Payment.telegram_charge_id==pay.telegram_payment_charge_id))).scalar_one_or_none(): return
        s.add(Payment(user_id=u.id,product="vip_30d",stars=pay.total_amount,payload=pay.invoice_payload,telegram_charge_id=pay.telegram_payment_charge_id))
        base=u.vip_until if u.vip_until and u.vip_until>datetime.utcnow() else datetime.utcnow()
        u.vip_until=base+timedelta(days=config.vip_days);await s.commit()
    await m.answer("⭐ VIP активирован. Спасибо!")

class AdminState(StatesGroup):
    search = State()
    broadcast = State()

def is_admin(user_id, config):
    return user_id in config.admin_ids

async def audit(s, admin_id, action, target_id=None, details=None):
    s.add(AuditLog(admin_tg_id=admin_id, action=action, target_id=target_id, details=details))

def admin_home_text():
    return "🛡 <b>АДМИН-ПАНЕЛЬ</b>\n\n«Орбита — Венера-Юпитер»\n\nВыберите раздел:"

@r.message(Command("myid"))
async def myid_command(m: Message):
    await m.answer(f"🆔 Ваш Telegram ID: <code>{m.from_user.id}</code>")

@r.message(Command("admin"))
async def admin_cmd(m:Message,config):
    if not is_admin(m.from_user.id, config): return
    await m.answer(admin_home_text(), reply_markup=admin())

@r.callback_query(F.data=="adm:home")
async def adm_home(c,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    await c.message.edit_text(admin_home_text(), reply_markup=admin()); await c.answer()

@r.callback_query(F.data=="adm:stats")
async def stats(c,db,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    async with db.session() as s:
        users=await s.scalar(select(func.count()).select_from(User)) or 0
        active=await s.scalar(select(func.count()).select_from(User).where(User.is_active==True,User.deleted_at==None)) or 0
        banned=await s.scalar(select(func.count()).select_from(User).where(User.is_banned==True)) or 0
        pending=await s.scalar(select(func.count()).select_from(User).where(User.moderation_status=="pending")) or 0
        photos=await s.scalar(select(func.count()).select_from(Photo).where(Photo.moderation_status=="pending")) or 0
        reports=await s.scalar(select(func.count()).select_from(Report).where(Report.status=="new")) or 0
        payments=await s.scalar(select(func.count()).select_from(Payment)) or 0
        revenue=await s.scalar(select(func.coalesce(func.sum(Payment.stars),0))) or 0
        vip_users=await s.scalar(select(func.count()).select_from(User).where(User.vip_until>datetime.utcnow())) or 0
    await c.message.edit_text(
        f"📊 <b>СТАТИСТИКА</b>\n\n👥 Всего: <b>{users}</b>\n🟢 Активных: <b>{active}</b>\n"
        f"🚫 Заблокировано: <b>{banned}</b>\n🖼 Анкет на модерации: <b>{pending}</b>\n"
        f"📷 Фото на модерации: <b>{photos}</b>\n🚨 Новых жалоб: <b>{reports}</b>\n"
        f"⭐ VIP сейчас: <b>{vip_users}</b>\n💳 Платежей: <b>{payments}</b>\n"
        f"💰 Выручка: <b>{revenue} Stars</b>", reply_markup=admin_back())
    await c.answer()

@r.callback_query(F.data=="adm:users")
async def adm_users(c,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    await c.message.edit_text("👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n\nИспользуйте /admin_search и отправьте Telegram ID, @username или имя.",reply_markup=admin_back())
    await c.answer()

@r.message(Command("admin_search"))
async def admin_search_start(m,state,config):
    if not is_admin(m.from_user.id, config): return
    await state.set_state(AdminState.search); await m.answer("🔎 Отправьте Telegram ID, @username или имя пользователя.")

@r.message(AdminState.search)
async def admin_search_run(m,state,db,config):
    if not is_admin(m.from_user.id, config): return
    q=(m.text or "").strip()
    async with db.session() as s:
        if q.isdigit(): stmt=select(User).where(User.tg_id==int(q)).limit(10)
        elif q.startswith("@"): stmt=select(User).where(User.username.ilike(q[1:])).limit(10)
        else: stmt=select(User).where(User.name.ilike(f"%{q}%")).limit(10)
        users=(await s.execute(stmt)).scalars().all()
    await state.clear()
    if not users: return await m.answer("Ничего не найдено.",reply_markup=admin())
    for u in users:
        await m.answer(
            f"👤 <b>{u.name or 'Без имени'}</b>, {u.age or '—'}\nID: <code>{u.tg_id}</code>\n"
            f"@{u.username or '—'}\nСтатус: {u.moderation_status}\n"
            f"VIP: {'✅' if await is_vip(u) else '❌'}\nБан: {'🚫' if u.is_banned else 'нет'}",
            reply_markup=user_actions(u.id))

@r.callback_query(F.data.startswith("adm:user:"))
async def adm_user(c,db,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    uid=int(c.data.split(":")[2])
    async with db.session() as s: u=await s.get(User,uid)
    if not u: return await c.answer("Не найдено",show_alert=True)
    await c.message.edit_text(
        f"👤 <b>{u.name or 'Без имени'}</b>, {u.age or '—'}\nTelegram ID: <code>{u.tg_id}</code>\n"
        f"Username: @{u.username or '—'}\nГород: {u.city or '—'}\n"
        f"Модерация: {u.moderation_status}\nАктивен: {'✅' if u.is_active else '❌'}\n"
        f"Бан: {'🚫' if u.is_banned else 'нет'}\nVIP до: {u.vip_until or '—'}",
        reply_markup=user_actions(u.id)); await c.answer()

@r.callback_query(F.data.startswith(("adm:ban_user:","adm:unban_user:","adm:vip_user:","adm:unvip_user:")))
async def adm_user_action(c,db,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    action,uid=c.data.rsplit(":",1); uid=int(uid)
    async with db.session() as s:
        u=await s.get(User,uid)
        if not u: return await c.answer("Не найдено",show_alert=True)
        if action=="adm:ban_user": u.is_banned=True; u.is_active=False; label="заблокирован"
        elif action=="adm:unban_user":
            u.is_banned=False
            u.is_active=bool(u.moderation_status=="approved" and u.deleted_at is None)
            label="разблокирован"
        elif action=="adm:vip_user":
            base=u.vip_until if u.vip_until and u.vip_until>datetime.utcnow() else datetime.utcnow()
            u.vip_until=base+timedelta(days=30); label="VIP выдан на 30 дней"
        else: u.vip_until=None; label="VIP снят"
        await audit(s,c.from_user.id,action,uid); await s.commit()
    await c.answer(label,show_alert=True); await adm_user(c,db,config)

async def next_pending(s):
    return (await s.execute(select(User).where(User.moderation_status=="pending").order_by(User.id).limit(1))).scalar_one_or_none()

@r.callback_query(F.data=="adm:profiles")
async def adm_profiles(c,db,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    async with db.session() as s: u=await next_pending(s)
    if not u: return await c.message.edit_text("🖼 Очередь анкет пуста.",reply_markup=admin_back())
    await c.message.edit_text(
        f"👤 <b>АНКЕТА НА МОДЕРАЦИИ</b>\n\n✨ {u.name or '—'}, {u.age or '—'}\n"
        f"📍 {u.city or '—'}\n\n{u.bio or '—'}\n\nTelegram ID: <code>{u.tg_id}</code>",
        reply_markup=moderate("profile",u.id)); await c.answer()

@r.callback_query(F.data=="adm:photos")
async def adm_photos(c,db,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    async with db.session() as s:
        p=(await s.execute(select(Photo).where(Photo.moderation_status=="pending").order_by(Photo.id).limit(1))).scalar_one_or_none()
        if not p: return await c.message.edit_text("📷 Очередь фото пуста.",reply_markup=admin_back())
        u=await s.get(User,p.user_id)
    await c.message.answer_photo(p.file_id,caption=f"📷 Фото на модерации\n👤 {u.name or '—'}, {u.age or '—'}",reply_markup=moderate("photo",p.id))
    await c.answer()

@r.callback_query(F.data.startswith("mod:"))
async def mod_action(c,db,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    _,action,kind,sid=c.data.split(":"); obj_id=int(sid); target_tg=None
    async with db.session() as s:
        if kind=="profile":
            u=await s.get(User,obj_id)
            if not u: return await c.answer("Не найдено",show_alert=True)
            target_tg=u.tg_id
            if action=="approve": u.moderation_status="approved"; u.is_active=True; label="Анкета одобрена"
            elif action=="reject": u.moderation_status="rejected"; u.is_active=False; label="Анкета отклонена"
            elif action=="ban": u.is_banned=True; u.is_active=False; u.moderation_status="rejected"; label="Пользователь заблокирован"
            elif action=="next":
                u2=(await s.execute(select(User).where(User.moderation_status=="pending",User.id>u.id).order_by(User.id).limit(1))).scalar_one_or_none()
                if u2:
                    u=u2
                    label="Следующая"
                else:
                    label="Это последняя анкета"
            else: return await c.answer()
            if action!="next": await audit(s,c.from_user.id,f"moderation_{action}",u.id)
        else:
            p=await s.get(Photo,obj_id)
            if not p: return await c.answer("Не найдено",show_alert=True)
            u=await s.get(User,p.user_id)
            if not u: return await c.answer("Пользователь не найден",show_alert=True)
            target_tg=u.tg_id
            if action=="approve": p.moderation_status="approved"; label="Фото одобрено"
            elif action=="reject": p.moderation_status="rejected"; label="Фото отклонено"
            elif action=="ban":
                u=await s.get(User,p.user_id); u.is_banned=True; u.is_active=False; target_tg=u.tg_id; label="Пользователь заблокирован"
            elif action=="next":
                p2=(await s.execute(select(Photo).where(Photo.moderation_status=="pending",Photo.id>p.id).order_by(Photo.id).limit(1))).scalar_one_or_none()
                if p2:
                    p=p2
                    label="Следующая"
                else:
                    label="Это последнее фото"
            else: return await c.answer()
            if action!="next": await audit(s,c.from_user.id,f"photo_{action}",p.user_id)
        await s.commit()
    if action in ("approve","reject") and target_tg:
        try: await c.bot.send_message(target_tg,f"🔔 Модерация: {label}.")
        except Exception: pass
    await c.answer(label,show_alert=True)
    if kind=="profile": await adm_profiles(c,db,config)
    else: await adm_photos(c,db,config)

@r.callback_query(F.data=="adm:reports")
async def adm_reports(c,db,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    async with db.session() as s:
        rep=(await s.execute(select(Report).where(Report.status=="new").order_by(Report.id).limit(1))).scalar_one_or_none()
        if not rep: return await c.message.edit_text("🚨 Новых жалоб нет.",reply_markup=admin_back())
        u=await s.get(User,rep.reported_id)
    await c.message.edit_text(f"🚨 <b>ЖАЛОБА #{rep.id}</b>\n\nНа: {u.name or '—'}, {u.age or '—'}\n"
                              f"Причина: {rep.reason}\nTelegram ID: <code>{u.tg_id}</code>",
                              reply_markup=report_actions(rep.id,rep.reported_id)); await c.answer()

@r.callback_query(F.data=="adm:reports_next")
async def reports_next(c,db,config): await adm_reports(c,db,config)

@r.callback_query(F.data.startswith(("adm:report_close:","adm:report_ban:")))
async def report_action(c,db,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    action,rid=c.data.rsplit(":",1); rid=int(rid)
    async with db.session() as s:
        rep=await s.get(Report,rid)
        if not rep: return await c.answer("Не найдено",show_alert=True)
        rep.status="closed"
        if action=="adm:report_ban":
            u=await s.get(User,rep.reported_id); u.is_banned=True; u.is_active=False
            await audit(s,c.from_user.id,"report_ban",u.id,rep.reason); label="Пользователь заблокирован"
        else:
            await audit(s,c.from_user.id,"report_close",rep.reported_id,rep.reason); label="Жалоба закрыта"
        await s.commit()
    await c.answer(label,show_alert=True); await adm_reports(c,db,config)

@r.callback_query(F.data=="adm:payments")
async def adm_payments(c,db,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    async with db.session() as s:
        count=await s.scalar(select(func.count()).select_from(Payment)) or 0
        total=await s.scalar(select(func.coalesce(func.sum(Payment.stars),0))) or 0
        last=(await s.execute(select(Payment).order_by(Payment.id.desc()).limit(10))).scalars().all()
    lines=[f"💳 <b>ПЛАТЕЖИ</b>\nВсего: {count}\nStars: {total}\n"]
    lines += [f"#{p.id} • {p.stars} ⭐ • {p.product} • {p.created_at:%Y-%m-%d %H:%M}" for p in last]
    await c.message.edit_text("\n".join(lines),reply_markup=admin_back()); await c.answer()

@r.callback_query(F.data=="adm:bans")
async def adm_bans(c,db,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    async with db.session() as s:
        users=(await s.execute(select(User).where(User.is_banned==True).order_by(User.id.desc()).limit(20))).scalars().all()
    text="🚫 <b>БАНЫ</b>\n\n"+("\n".join(f"#{u.id} {u.name or '—'} • <code>{u.tg_id}</code>" for u in users) if users else "Нет заблокированных.")
    await c.message.edit_text(text,reply_markup=admin_back()); await c.answer()

@r.callback_query(F.data=="adm:broadcast")
async def adm_broadcast(c,state,config):
    if not is_admin(c.from_user.id, config): return await c.answer()
    await state.set_state(AdminState.broadcast)
    await c.message.edit_text("📢 <b>РАССЫЛКА</b>\n\nОтправьте текст для всех активных пользователей.\nДля отмены: /cancel")
    await c.answer()

@r.message(Command("cancel"))
async def admin_cancel(m,state):
    await state.clear(); await m.answer("Отменено.",reply_markup=main())

@r.message(AdminState.broadcast)
async def admin_broadcast_send(m,state,db,config):
    if not is_admin(m.from_user.id, config): return
    payload=m.text or m.caption
    if not payload: return await m.answer("Отправьте текстовое сообщение.")
    async with db.session() as s:
        users=(await s.execute(select(User).where(User.is_active==True,User.is_banned==False,User.deleted_at==None))).scalars().all()
    ok=fail=0
    for u in users:
        try:
            await m.bot.send_message(u.tg_id,payload); ok+=1
            await asyncio.sleep(0.05)
        except Exception: fail+=1
    async with db.session() as s:
        await audit(s,m.from_user.id,"broadcast",None,f"ok={ok},fail={fail}"); await s.commit()
    await state.clear(); await m.answer(f"📢 Рассылка завершена.\n\n✅ {ok}\n❌ {fail}",reply_markup=admin())

@r.message(Command("help"))
async def help_(m): await m.answer("🔎 Смотреть · 📍 Поиск рядом · ❤️ лайки · 💞 совпадения · ⭐ VIP · 🗑 удаление · /restore восстановление · /admin для администраторов · /myid — ваш Telegram ID")

@r.message()
async def fallback(m,db,config):
    # Lightweight anti-spam: repeated freeform messages are throttled per user in memory.
    key=f"{m.from_user.id}"
    now=asyncio.get_running_loop().time()
    last=getattr(fallback,"last",{})
    if now-last.get(key,0)<config.antispam_seconds:return
    last[key]=now
    fallback.last=last
