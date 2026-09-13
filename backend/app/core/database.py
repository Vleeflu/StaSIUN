from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# prepare_threshold=None disables psycopg3's automatic prepared statements. They
# break on transaction-mode connection poolers (Supabase Supavisor, PgBouncer),
# which don't keep a fixed backend across statements. Harmless on a direct
# connection, so it stays on for local Docker too.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"prepare_threshold": None},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
