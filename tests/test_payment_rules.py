def test_payment_rule():
    user_id=123; payload=f'vip:{user_id}:999'; currency='XTR'
    assert currency=='XTR' and payload.startswith(f'vip:{user_id}:')
