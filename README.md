# Орбита — Венера-Юпитер PRO

Production-ready foundation for Telegram dating bot.

> `.env` намеренно не входит в архив. Создайте его из `.env.production.example` и заполните своими секретами.

## Стек
- Python 3.12 / aiogram 3
- PostgreSQL 16
- Redis 7 (FSM + anti-spam + daily like counters)
- Alembic migrations
- Telegram Stars XTR for VIP
- Daily local PostgreSQL dump via `pg_dump`
- Telegram admin panel inside the bot
- **Long polling** — без домена, HTTPS, Caddy и webhook на текущем этапе

## Быстрый старт
1. Скопируйте `.env.production.example` в `.env`.
2. Укажите `BOT_TOKEN`, `ADMIN_IDS`, пароль PostgreSQL и `DATABASE_URL`.
3. Запустите:
   ```bash
   docker compose up -d --build
   ```
4. Проверьте логи:
   ```bash
   docker compose logs -f bot
   ```
5. В Telegram отправьте `/admin` с аккаунта, чей ID указан в `ADMIN_IDS`.

Узнать свой Telegram ID можно командой `/myid`.

## Админ-панель
Админ-панель полностью внутри Telegram. Отдельного сайта для неё нет.

Разделы:
- 📊 статистика
- 👥 поиск пользователей
- 🖼 модерация анкет
- 📷 модерация фото
- 🚨 жалобы
- 💳 платежи
- 📢 рассылка
- 🚫 баны

## Данные и миграции
Схема PostgreSQL создаётся/обновляется автоматически перед запуском бота командой:
```bash
alembic upgrade head
```

## Резервные копии
Сервис `backup` создаёт PostgreSQL dump раз в сутки и хранит локальные копии 14 дней. Для полноценного disaster recovery позже рекомендуется добавить off-site/S3-копирование.

## Позже
Когда появится домен и понадобится webhook, runtime можно отдельным обновлением перевести с long polling на HTTPS webhook.
