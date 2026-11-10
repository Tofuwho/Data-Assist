import logging
import os
import sys

from alembic.config import Config
from sqlalchemy import inspect

from alembic import command
from app.config import API_DIR, settings
from app.models import database
from app.models.entities import Membership, User, Workspace
from app.services.auth import hash_password

logger = logging.getLogger(__name__)


def _is_test_runtime() -> bool:
    return (
        settings.ENVIRONMENT == "test"
        or "pytest" in sys.modules
        or "PYTEST_CURRENT_TEST" in os.environ
    )


def ensure_local_sqlite_schema() -> None:
    """Initialize local SQLite schema via Alembic if tables do not exist yet."""
    if _is_test_runtime() or not settings.DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(database.engine)
    if inspector.has_table("users"):
        return

    alembic_ini = API_DIR / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    logger.info("Bootstrapping local SQLite database schema via Alembic...")
    command.upgrade(alembic_cfg, "head")


def seed_dev_demo_accounts() -> None:
    """Seed demo Admin and Steward accounts in empty local development databases."""
    if _is_test_runtime() or settings.ENVIRONMENT != "development":
        return

    db = database.SessionLocal()
    try:
        if db.query(User.id).first() is not None:
            return

        admin_user = User(
            email="admin@cleardata.io",
            password_hash=hash_password("Password123!"),
            name="Alice Admin",
        )
        steward_user = User(
            email="steward@cleardata.io",
            password_hash=hash_password("Password123!"),
            name="Sam Steward",
        )
        db.add_all([admin_user, steward_user])
        db.flush()

        acme_ws = Workspace(name="Acme Operations")
        global_ws = Workspace(name="Global Data Office")
        db.add_all([acme_ws, global_ws])
        db.flush()

        db.add_all(
            [
                Membership(user_id=admin_user.id, workspace_id=acme_ws.id, role="admin"),
                Membership(user_id=steward_user.id, workspace_id=acme_ws.id, role="steward"),
                Membership(user_id=steward_user.id, workspace_id=global_ws.id, role="admin"),
            ]
        )
        db.commit()
        logger.info("Seeded development demo accounts (admin@cleardata.io, steward@cleardata.io).")
    except Exception:
        db.rollback()
        logger.exception("Failed seeding development demo accounts.")
    finally:
        db.close()
