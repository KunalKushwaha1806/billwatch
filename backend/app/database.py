"""SQLite database setup via SQLAlchemy."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./billwatch.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables from ORM models."""
    from app.models import (  # noqa: F401 — import triggers table registration
        Payment,
        CheckoutSession,
        RiskSignal,
        RecoveryAction,
        AuditEntry,
    )
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables — used before reloading a batch."""
    from app.models import (  # noqa: F401
        Payment,
        CheckoutSession,
        RiskSignal,
        RecoveryAction,
        AuditEntry,
    )
    Base.metadata.drop_all(bind=engine)
