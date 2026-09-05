from sqlalchemy import select,func,or_
from .db import User,Photo,Report,Payment

async def dashboard(session):
    return {
        "users": await session.scalar(select(func.count()).select_from(User)),
        "active": await session.scalar(select(func.count()).select_from(User).where(User.is_active==True,User.deleted_at==None)),
        "pending_profiles": await session.scalar(select(func.count()).select_from(User).where(User.moderation_status=="pending")),
        "pending_photos": await session.scalar(select(func.count()).select_from(Photo).where(Photo.moderation_status=="pending")),
        "reports": await session.scalar(select(func.count()).select_from(Report).where(Report.status=="new")),
        "payments": await session.scalar(select(func.count()).select_from(Payment)),
    }

async def pending_profile(session):
    return (await session.execute(select(User).where(User.moderation_status=="pending").order_by(User.id).limit(1))).scalar_one_or_none()

async def pending_photo(session):
    return (await session.execute(select(Photo).where(Photo.moderation_status=="pending").order_by(Photo.id).limit(1))).scalar_one_or_none()
