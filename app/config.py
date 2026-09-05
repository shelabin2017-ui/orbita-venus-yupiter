import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: set[int]
    database_url: str
    redis_url: str
    min_age: int
    max_age: int
    free_daily_likes: int
    vip_daily_likes: int
    max_photos: int
    antispam_seconds: int
    stars_vip_price: int
    vip_days: int
    backup_dir: str

def load_config():
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("❌ BOT_TOKEN не найден! Добавь BOT_TOKEN в файл .env")

    admin_ids = {
        int(x.strip())
        for x in os.getenv("ADMIN_IDS", "").split(",")
        if x.strip()
    }
    if not admin_ids:
        raise RuntimeError("❌ ADMIN_IDS не найден! Добавь Telegram ID администратора в .env")

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://orbita:change_me@postgres:5432/orbita",
    ).strip()
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+asyncpg://" + database_url[len("postgresql://"): ]

    return Config(
        bot_token=token,
        admin_ids=admin_ids,
        database_url=database_url,
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        min_age=int(os.getenv("MIN_AGE", "18")),
        max_age=int(os.getenv("MAX_AGE", "99")),
        free_daily_likes=int(os.getenv("FREE_DAILY_LIKES", "20")),
        vip_daily_likes=int(os.getenv("VIP_DAILY_LIKES", "200")),
        max_photos=int(os.getenv("MAX_PHOTOS", "5")),
        antispam_seconds=int(os.getenv("ANTISPAM_SECONDS", "2")),
        stars_vip_price=int(os.getenv("STARS_VIP_PRICE", "100")),
        vip_days=int(os.getenv("VIP_DAYS", "30")),
        backup_dir=os.getenv("BACKUP_DIR", "/backups"),
    )
