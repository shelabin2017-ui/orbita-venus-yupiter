def test_runtime_modules_import():
    from app import activity, admin_service, anti_spam, config, db, features, handlers, keyboards, main, match_features, payments, promo, redis_store, secret_signal, services, spark, universe

    modules = [
        activity,
        admin_service,
        anti_spam,
        config,
        db,
        features,
        handlers,
        keyboards,
        main,
        match_features,
        payments,
        promo,
        redis_store,
        secret_signal,
        services,
        spark,
        universe,
    ]
    assert all(module is not None for module in modules)
