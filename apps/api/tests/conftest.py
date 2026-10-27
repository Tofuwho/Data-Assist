import os
import warnings
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.database import Base, get_db


def create_test_engine() -> tuple[Engine, str]:
    """Create test engine: PostgreSQL if available/configured, otherwise fallback to SQLite."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url and ("postgresql" in db_url or "postgres" in db_url):
        try:
            pg_engine = create_engine(db_url, pool_pre_ping=True)
            with pg_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return pg_engine, "postgresql"
        except Exception as exc:
            warnings.warn(
                f"Configured PostgreSQL database is not reachable ({exc}). "
                "Falling back to SQLite in-memory for testing.",
                stacklevel=2,
            )

    # In-memory SQLite with foreign keys enforced
    sqlite_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(sqlite_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return sqlite_engine, "sqlite"


_engine, _db_type = create_test_engine()


@pytest.fixture(scope="session")
def test_engine() -> Engine:
    """Session-scoped database engine."""
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(scope="session")
def db_type() -> str:
    """Return database type ('postgresql' or 'sqlite')."""
    return _db_type


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Yield a database session and clean up after each test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Clean up data between tests in foreign-key dependency order
        with test_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


@pytest.fixture
def client(test_engine: Engine) -> Generator[TestClient, None, None]:
    """Yield a TestClient configured with test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

    # Clean up data between tests
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def client_and_db(client: TestClient) -> TestClient:
    """Backward compatibility fixture for existing tests."""
    return client
