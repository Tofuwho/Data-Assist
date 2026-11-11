import pytest
from sqlalchemy.orm import sessionmaker

from app.config import DEFAULT_INSECURE_SECRET_KEY, Settings
from app.models import database
from app.models.entities import Membership, User, Workspace
from app.services import auth as auth_service
from app.services import seed as seed_service


def test_default_settings_uses_sqlite_when_unconfigured(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    fresh = Settings(_env_file=None)
    assert fresh.DATABASE_URL.startswith("sqlite:///")
    assert fresh.DATABASE_URL.endswith("cleardata.db")


def test_seed_dev_demo_accounts_is_idempotent(test_engine, monkeypatch):
    # Clean tables first
    with test_engine.begin() as conn:
        for table in reversed(database.Base.metadata.sorted_tables):
            conn.execute(table.delete())

    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(database, "SessionLocal", testing_session_local)
    monkeypatch.setattr(seed_service, "_is_test_runtime", lambda: False)
    monkeypatch.setattr(seed_service.settings, "ENVIRONMENT", "development")

    # First run seeds Alice Admin & Sam Steward
    seed_service.seed_dev_demo_accounts()
    # Second run is a no-op
    seed_service.seed_dev_demo_accounts()

    db = testing_session_local()
    try:
        users = db.query(User).order_by(User.email.asc()).all()
        assert [u.email for u in users] == ["admin@cleardata.io", "steward@cleardata.io"]
        assert auth_service.verify_password("Password123!", users[0].password_hash)
        assert auth_service.verify_password("Password123!", users[1].password_hash)

        workspaces = db.query(Workspace).all()
        assert len(workspaces) == 2
        memberships = db.query(Membership).all()
        assert len(memberships) == 3
    finally:
        db.close()
        with test_engine.begin() as conn:
            for table in reversed(database.Base.metadata.sorted_tables):
                conn.execute(table.delete())


def test_production_environment_rejects_default_or_short_secret_key():
    insecure = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY=DEFAULT_INSECURE_SECRET_KEY,
    )
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        insecure.validate_runtime_security()

    too_short = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY="short-secret",
    )
    with pytest.raises(RuntimeError, match="32 characters"):
        too_short.validate_runtime_security()

    strong = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY="a" * 32,
    )
    strong.validate_runtime_security()


def test_seed_dev_demo_accounts_skips_production(test_engine, monkeypatch):
    with test_engine.begin() as conn:
        for table in reversed(database.Base.metadata.sorted_tables):
            conn.execute(table.delete())

    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(database, "SessionLocal", testing_session_local)
    monkeypatch.setattr(seed_service, "_is_test_runtime", lambda: False)
    monkeypatch.setattr(seed_service.settings, "ENVIRONMENT", "production")

    seed_service.seed_dev_demo_accounts()

    db = testing_session_local()
    try:
        assert db.query(User).count() == 0
    finally:
        db.close()

