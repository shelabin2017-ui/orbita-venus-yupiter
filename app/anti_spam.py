from redis.asyncio import Redis
class AntiSpam:
    def __init__(self,redis,cooldown=2): self.redis=redis; self.cooldown=cooldown
    async def allowed(self,user_id,action='msg'):
        key=f'anti:{action}:{user_id}'; return bool(await self.redis.set(key,'1',nx=True,ex=self.cooldown))
    async def daily_limit(self,user_id,limit):
        from datetime import datetime,timezone
        now=datetime.now(timezone.utc); key=f'likes:{user_id}:{now.date().isoformat()}'
        n=await self.redis.incr(key); await self.redis.expire(key,90000)
        return n<=limit
