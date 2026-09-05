from contextvars import ContextVar
from urllib.parse import quote
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

_current_user_is_admin: ContextVar[bool] = ContextVar("current_user_is_admin", default=False)

def set_current_user_is_admin(value: bool):
    _current_user_is_admin.set(value)

def main():
    rows = [
        [KeyboardButton(text="🔎 Смотреть"), KeyboardButton(text="💞 Совпадения")],
        [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="✏️ Изменить")],
        [KeyboardButton(text="📍 Поиск рядом"), KeyboardButton(text="⭐ VIP")],
        [KeyboardButton(text="⭐ Stars"), KeyboardButton(text="🎮 Игры")],
        [KeyboardButton(text="🌌 О проекте")],
    ]
    if _current_user_is_admin.get():
        rows.append([KeyboardButton(text="🛡 Админ-панель")])
    rows.append([KeyboardButton(text="🗑 Удалить анкету")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def gender(prefix):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Мужчина", callback_data=f"{prefix}:male"), InlineKeyboardButton(text="👩 Женщина", callback_data=f"{prefix}:female")],
        [InlineKeyboardButton(text="🌐 Неважно", callback_data=f"{prefix}:any")]])

def profile(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Нравится", callback_data=f"like:{uid}"), InlineKeyboardButton(text="👎 Дальше", callback_data=f"skip:{uid}")],
        [InlineKeyboardButton(text="💬 Написать", callback_data=f"chat:start:{uid}"), InlineKeyboardButton(text="🚩 Жалоба", callback_data=f"report:{uid}")],
        [InlineKeyboardButton(text="🚫 Блок", callback_data=f"block:{uid}")]])

def match_profile(uid, username=None):
    greeting = "Привет, я с Орбиты Венеры-Юпитера! 🌌"
    if username:
        contact = InlineKeyboardButton(text="💬 Открыть Telegram", url=f"https://t.me/{username}?text={quote(greeting)}")
    else:
        contact = InlineKeyboardButton(text="👤 Открыть профиль", url=f"tg://user?id={uid}")
    return InlineKeyboardMarkup(inline_keyboard=[
        [contact],
        [InlineKeyboardButton(text="📨 Написать через бота", callback_data=f"chat:start:{uid}")],
        [InlineKeyboardButton(text="👋 Отправить приветствие", callback_data=f"match:greet:{uid}")],
    ])

def chat_cancel():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Завершить диалог", callback_data="chat:cancel")]])

def admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats"), InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:users")],
        [InlineKeyboardButton(text="🖼 Анкеты", callback_data="adm:profiles"), InlineKeyboardButton(text="📷 Фото", callback_data="adm:photos")],
        [InlineKeyboardButton(text="🚨 Жалобы", callback_data="adm:reports"), InlineKeyboardButton(text="💳 Платежи", callback_data="adm:payments")],
        [InlineKeyboardButton(text="⭐ Stars", callback_data="adm:stars")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm:broadcast"), InlineKeyboardButton(text="🚫 Баны", callback_data="adm:bans")]])

def admin_back():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="adm:home")]])

def moderate(kind, id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"mod:approve:{kind}:{id}"), InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mod:reject:{kind}:{id}")],
        [InlineKeyboardButton(text="🔨 Бан", callback_data=f"mod:ban:{kind}:{id}")],
        [InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="adm:home")]])

def report_actions(id, reported_user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Открыть", callback_data=f"adm:user:{reported_user_id}")],
        [InlineKeyboardButton(text="⚠️ Закрыть", callback_data=f"adm:report_close:{id}"), InlineKeyboardButton(text="🔨 Бан", callback_data=f"adm:report_ban:{id}")],
        [InlineKeyboardButton(text="➡️ Следующая", callback_data="adm:reports_next")],
        [InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="adm:home")]])

def user_actions(id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔨 Заблокировать", callback_data=f"adm:ban_user:{id}"), InlineKeyboardButton(text="♻️ Разблокировать", callback_data=f"adm:unban_user:{id}")],
        [InlineKeyboardButton(text="⭐ Выдать VIP", callback_data=f"adm:vip_user:{id}"), InlineKeyboardButton(text="❌ Снять VIP", callback_data=f"adm:unvip_user:{id}")],
        [InlineKeyboardButton(text="⭐ Начислить Stars", callback_data=f"adm:stars:{id}"), InlineKeyboardButton(text="📜 История Stars", callback_data=f"adm:stars_history:{id}")],
        [InlineKeyboardButton(text="⬅️ Админ-панель", callback_data="adm:home")]])

def vip(price):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"⭐ VIP — {price} Stars", callback_data="buy:vip")]])

def edit_fields():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Имя", callback_data="edit:name"), InlineKeyboardButton(text="🎂 Возраст", callback_data="edit:age")],
        [InlineKeyboardButton(text="⚧ Пол", callback_data="edit:gender"), InlineKeyboardButton(text="🔎 Кого ищу", callback_data="edit:looking")],
        [InlineKeyboardButton(text="🏙 Город", callback_data="edit:city"), InlineKeyboardButton(text="📝 О себе", callback_data="edit:bio")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="edit:cancel")]])

def report_reasons(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Спам", callback_data=f"report_reason:spam:{uid}"), InlineKeyboardButton(text="🔞 Контент 18+", callback_data=f"report_reason:adult:{uid}")],
        [InlineKeyboardButton(text="💰 Мошенничество", callback_data=f"report_reason:scam:{uid}"), InlineKeyboardButton(text="⚠️ Другое", callback_data=f"report_reason:other:{uid}")],
        [InlineKeyboardButton(text="Отмена", callback_data="report_reason:cancel:0")]])

def matches_actions():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔎 Смотреть анкеты", callback_data="match:browse")],[InlineKeyboardButton(text="⬅️ Меню", callback_data="match:menu")]])

def confirm_delete():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Удалить", callback_data="delete:yes"), InlineKeyboardButton(text="Отмена", callback_data="delete:no")]])
