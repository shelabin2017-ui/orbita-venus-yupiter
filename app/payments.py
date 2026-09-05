from datetime import datetime,timedelta
from sqlalchemy import select
from .db import Payment

async def activate_vip(session,user,successful_payment,days):
    charge=successful_payment.telegram_payment_charge_id
    existing=(await session.execute(select(Payment).where(Payment.telegram_charge_id==charge))).scalar_one_or_none()
    if existing:return False
    session.add(Payment(
        user_id=user.id, product="vip_30d",
        stars=successful_payment.total_amount,
        payload=successful_payment.invoice_payload,
        telegram_charge_id=charge
    ))
    base=user.vip_until if user.vip_until and user.vip_until>datetime.utcnow() else datetime.utcnow()
    user.vip_until=base+timedelta(days=days)
    await session.commit()
    return True
