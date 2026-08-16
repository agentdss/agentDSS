"""
AgentDSS — Track B — Database connection setup (Week 1, task 2)

Reads connection config from environment variables so the same code
works locally, in CI, and in whatever deployment you use later —
no hardcoded credentials in source, ever.

Usage:
    from database import get_db, init_db

    init_db()  # run once, e.g. at app startup — creates tables if missing

    with get_db() as db:
        agent = db.query(Agent).first()
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

# --- Config ---------------------------------------------------------------
# Set these as real environment variables; do not commit actual credentials.
# For local dev: export AGENTDSS_DB_URL="postgresql://user:pass@localhost:5432/agentdss"
DB_URL = os.environ.get(
    "AGENTDSS_DB_URL",
    "sqlite:///./agentdss_dev.db",  # falls back to local SQLite if unset, for quick local testing
)

# SQLite needs this flag for multi-thread use (e.g. under FastAPI); Postgres ignores it.
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

engine = create_engine(DB_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables defined in models.py if they don't already exist."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db():
    """
    Context-managed session — guarantees the connection is closed even
    if the calling code raises. Use as:
        with get_db() as db:
            db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Smoke test: create tables, insert one Agent, read it back, confirm round-trip.
    from models import Agent, AgentRole

    init_db()
    print(f"Connected to: {DB_URL}")

    with get_db() as db:
        test_agent = Agent(
            name="Supplier Manager",
            role=AgentRole.SUPPLIER,
            description="Handles supplier delay disruptions",
            prompt_template_version="v1",
        )
        db.add(test_agent)
        db.flush()
        inserted_id = test_agent.id

    with get_db() as db:
        fetched = db.query(Agent).filter(Agent.id == inserted_id).first()
        assert fetched is not None, "Round-trip failed — agent not found after commit"
        assert fetched.name == "Supplier Manager"
        print(f"Round-trip verified. Agent '{fetched.name}' (role={fetched.role.value}) persisted and re-read correctly.")
