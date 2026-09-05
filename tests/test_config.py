def test_required_config(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "test:token")
    monkeypatch.setenv("ADMIN_IDS", "1, 2")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@db/orbita")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    from app.config import load_config
    c = load_config()
    assert c.bot_token == "test:token"
    assert c.admin_ids == {1, 2}
    assert c.redis_url.startswith("redis://")
    assert c.database_url.startswith("postgresql+asyncpg://")
    assert not hasattr(c, "webhook_base_url")
    assert not hasattr(c, "admin_password")
