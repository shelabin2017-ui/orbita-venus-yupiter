# Архитектура — «Орбита — Венера-Юпитер»

## Runtime
- Telegram Bot API через **long polling**
- aiogram 3
- PostgreSQL + SQLAlchemy async
- Redis для FSM, anti-spam и дневного лимита лайков
- Alembic для миграций
- Telegram Stars (XTR) для VIP

## Меню пользователя
🔎 Смотреть | 💞 Совпадения
👤 Моя анкета | ✏️ Изменить
📍 Поиск рядом | ⭐ VIP
🗑 Удалить анкету

## Админ-панель Telegram
📊 Статистика
👥 Поиск пользователей
🖼 Анкеты на модерации
📷 Фото на модерации
🚨 Жалобы
💳 Платежи
📢 Рассылка
🚫 Баны

Доступ: только Telegram ID из `ADMIN_IDS`.

## Состояния анкеты
draft -> pending -> approved/rejected
`deleted_at != NULL` => soft delete
restore => pending

## Модерация
Фото: pending -> approved/rejected
Анкета: pending -> approved/rejected
Ban отключает `is_active`.

## VIP
Invoice -> pre_checkout -> successful_payment -> Payment ledger -> `vip_until`.

## Деплой
Текущий runtime не использует домен, HTTPS, Caddy или webhook.
