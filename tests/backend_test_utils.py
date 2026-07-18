"""Helpers to reconfigure the backend for isolated tests without reloading ORM models."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def configure_backend(tmp_path: Path, monkeypatch, **env: str):
    """Apply env, rebuild engine/session, recreate tables, return main module."""
    defaults = {
        "ATT_ENV": "development",
        "ATT_REQUIRE_AUTH": "false",
        "ATT_SECRET_KEY": "dev-test-secret",
        "ATT_DATA_DIR": str(tmp_path),
        "ATT_DATABASE_URL": f"sqlite:///{tmp_path / 'app.db'}",
        "ATT_STORAGE_BACKEND": "local",
        "ATT_USE_WORKER": "false",
        "ATT_ALLOW_YOUTUBE": "false",
        "ATT_BOOTSTRAP_ADMIN_EMAIL": "admin@localhost",
        "ATT_BOOTSTRAP_ADMIN_PASSWORD": "changeme",
        "ATT_CORS_ORIGINS": "http://localhost:5173",
        "ATT_MAX_UPLOAD_MB": "50",
    }
    defaults.update(env)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)

    import backend.config as config_mod

    new_settings = config_mod.Settings()
    config_mod.settings = new_settings

    import backend.db as db_mod
    import backend.auth as auth_mod
    import backend.storage as storage_mod
    import backend.jobs.manager as manager_mod
    import backend.jobs.runner as runner_mod
    import backend.events as events_mod
    import backend.main as main_mod
    import backend.worker as worker_mod

    for mod in (
        auth_mod,
        storage_mod,
        manager_mod,
        runner_mod,
        events_mod,
        main_mod,
        worker_mod,
        db_mod,
    ):
        if hasattr(mod, "settings"):
            monkeypatch.setattr(mod, "settings", new_settings, raising=False)

    engine = create_engine(
        new_settings.database_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    db_mod.engine = engine
    db_mod.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    # Ensure models are registered on Base
    import backend.models  # noqa: F401

    db_mod.Base.metadata.drop_all(bind=engine)
    db_mod.Base.metadata.create_all(bind=engine)

    storage_mod.reset_storage()
    auth_mod.ensure_bootstrap_admin()

    main_mod.data_dir = Path(new_settings.data_dir)
    main_mod.job_manager = manager_mod.JobManager(main_mod.data_dir)
    return main_mod
