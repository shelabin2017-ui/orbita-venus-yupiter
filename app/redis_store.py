from redis.asyncio import Redis
from aiogram.fsm.storage.redis import RedisStorage

def make_redis(url): return Redis.from_url(url,decode_responses=True)
def make_fsm_storage(redis): return RedisStorage(redis=redis)
