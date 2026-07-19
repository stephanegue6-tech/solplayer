import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./crimtrack.db")

# check_same_thread nécessaire uniquement pour SQLite (accès multi-thread
# de FastAPI/uvicorn). Sans effet sur PostgreSQL.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dépendance FastAPI : une session par requête, fermée à la fin."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
