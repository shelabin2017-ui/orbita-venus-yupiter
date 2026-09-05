# VPS/Docker deploy — «Орбита — Венера-Юпитер»

Текущая версия работает через **Telegram long polling**. Домен, HTTPS, Caddy и webhook сейчас не нужны.

## Требования
- Ubuntu 24.04 LTS
- Docker Engine + Compose plugin
- 2 CPU / 4 GB RAM — комфортный минимум

## 1. Подготовка
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl ufw
# Установите Docker Engine + Compose plugin по официальной инструкции Docker.
```

Firewall можно оставить закрытым для HTTP/HTTPS: боту нужен исходящий доступ в Telegram, PostgreSQL и Redis наружу не публикуются.

## 2. Развертывание
```bash
sudo mkdir -p /opt/orbita
sudo chown -R "$USER":"$USER" /opt/orbita
cd /opt/orbita
# распакуйте сюда архив проекта
cp .env.production.example .env
nano .env
```

Заполните обязательно:
- `BOT_TOKEN` — новый токен из BotFather
- `ADMIN_IDS` — ваш Telegram ID (его можно узнать командой `/myid`)
- `POSTGRES_PASSWORD` — длинный случайный пароль
- `DATABASE_URL` — тот же пароль, URL для PostgreSQL

Важно: пароль должен совпадать в `POSTGRES_PASSWORD` и `DATABASE_URL`.

## 3. Запуск
```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 bot
```

При старте контейнер бота сначала выполняет `alembic upgrade head`, затем запускает Telegram long polling.

## 4. Проверка
```bash
docker compose ps
docker compose logs -f bot
```

В логах должно появиться:
```text
🟢 Орбита запущена в режиме long polling
```

## 5. Админка
В `.env` укажите ваш Telegram ID в `ADMIN_IDS`. Затем в Telegram отправьте боту:
```text
/admin
```

Для проверки своего ID:
```text
/myid
```

Админ-панель работает **внутри Telegram** и не требует отдельного сайта.

## 6. Бэкапы
Контейнер `backup` делает PostgreSQL dump раз в сутки и хранит локальные копии 14 дней:
```bash
docker compose logs --tail=50 backup
docker compose exec backup ls -lh /backups
```

Для настоящего disaster recovery позже добавьте копирование `/backups` на другой сервер или S3-совместимое хранилище.

## 7. Telegram Stars
VIP оплачивается через Telegram Stars (XTR). Отдельный платёжный провайдер для цифрового VIP в этой схеме не нужен.

## 8. Обновление
```bash
cd /opt/orbita
docker compose up -d --build
```

Миграции применяются автоматически перед запуском бота.

## 9. Безопасность
- `.env` не коммитить и никому не отправлять.
- После утечки токена перевыпустить его в BotFather.
- PostgreSQL и Redis не публикуются наружу.
- Регулярно проверять восстановление backup на отдельной БД.

## Позже: webhook + домен
Когда понадобится webhook, можно отдельным обновлением вернуть HTTPS/Caddy/FastAPI и webhook-настройки. В текущей версии они намеренно удалены из runtime.
