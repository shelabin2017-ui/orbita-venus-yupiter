from datetime import datetime,timedelta
from math import radians,sin,cos,asin,sqrt
from sqlalchemy import select,func,and_,or_
from .db import User,Photo,Reaction,Match,Block

def distance_km(lat1,lon1,lat2,lon2):
    r=6371
    dlat=radians(lat2-lat1); dlon=radians(lon2-lon1)
    a=sin(dlat/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2*r*asin(sqrt(a))

async def get_user(s,tg_id): return (await s.execute(select(User).where(User.tg_id==tg_id))).scalar_one_or_none()

async def public_photos(s,user_id):
    return (await s.execute(select(Photo).where(Photo.user_id==user_id,Photo.moderation_status=="approved").order_by(Photo.position))).scalars().all()

async def is_vip(u): return bool(u.vip_until and u.vip_until>datetime.utcnow())

async def like_count_today(s,u):
    start=datetime.utcnow().replace(hour=0,minute=0,second=0,microsecond=0)
    return await s.scalar(select(func.count()).select_from(Reaction).where(Reaction.from_user_id==u.id,Reaction.kind=="like",Reaction.created_at>=start))

async def next_profile(s,me, radius=None, inactive_days=7):
    seen=select(Reaction.to_user_id).where(Reaction.from_user_id==me.id)
    freshness=datetime.utcnow()-timedelta(days=max(inactive_days,1))
    q=select(User).where(
        User.id!=me.id,
        User.is_active==True,
        User.is_banned==False,
        User.moderation_status=="approved",
        User.deleted_at==None,
        or_(User.last_active_at==None,User.last_active_at>=freshness),
        ~User.id.in_(seen),
    )
    if me.looking_for and me.looking_for!="any": q=q.where(User.gender==me.looking_for)
    rows=(await s.execute(q.order_by(User.last_active_at.desc().nullslast(),User.id).limit(100))).scalars().all()
    for u in rows:
        if await blocked(s,me.id,u.id): continue
        if radius and me.latitude is not None and u.latitude is not None:
            if distance_km(me.latitude,me.longitude,u.latitude,u.longitude)>radius: continue
        return u
    return None

async def blocked(s,a,b):
    q=select(Block).where(or_(and_(Block.blocker_id==a,Block.blocked_id==b),and_(Block.blocker_id==b,Block.blocked_id==a)))
    return (await s.execute(q)).scalar_one_or_none() is not None

async def react(s,me,other,kind):
    old=(await s.execute(select(Reaction).where(Reaction.from_user_id==me.id,Reaction.to_user_id==other.id))).scalar_one_or_none()
    if old: old.kind=kind
    else: s.add(Reaction(from_user_id=me.id,to_user_id=other.id,kind=kind))
    await s.commit()
    if kind!="like": return False
    reciprocal=(await s.execute(select(Reaction).where(Reaction.from_user_id==other.id,Reaction.to_user_id==me.id,Reaction.kind=="like"))).scalar_one_or_none()
    if not reciprocal:return False
    a,b=sorted((me.id,other.id))
    exists=(await s.execute(select(Match).where(Match.user_a_id==a,Match.user_b_id==b))).scalar_one_or_none()
    if not exists:s.add(Match(user_a_id=a,user_b_id=b));await s.commit()
    return True
