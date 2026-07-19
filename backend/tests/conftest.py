"""Fixtures pytest partagées.

Chaque session de tests utilise une base SQLite dédiée (fichier temporaire),
créée avant l'import de `app.main` pour que `DATABASE_URL` soit pris en
compte par `app.database` — jamais la base de développement (`crimtrack.db`)
ni une base de production.
"""

import os
import tempfile

import pytest

_tmp_db_fd, _TMP_DB_PATH = tempfile.mkstemp(prefix="crimtrack_test_", suffix=".db")
os.close(_tmp_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB_PATH}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from fastapi.testclient import TestClient  # noqa: E402

from app import auth, models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    os.remove(_TMP_DB_PATH)


@pytest.fixture(autouse=True)
def _clean_database():
    """Vide toutes les tables avant chaque test pour garantir leur isolation
    (la base sqlite est partagée pour toute la session de tests)."""
    yield
    session = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


def _create_user(db_session, *, email: str, role: str, nom: str = "Test", prenom: str = "User"):
    user = models.Utilisateur(
        email=email,
        hashed_password=auth.hash_password("Test1234!"),
        nom=nom,
        prenom=prenom,
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _token_for(user: models.Utilisateur) -> str:
    return auth.create_access_token(subject=user.id, role=user.role)


@pytest.fixture
def make_user_and_token(db_session):
    """Fabrique (utilisateur, token) pour un rôle donné, sans passer par
    l'endpoint /auth/login (plus rapide, évite le rate-limit en test)."""

    counter = {"n": 0}

    def _factory(role: str = "enqueteur"):
        counter["n"] += 1
        user = _create_user(db_session, email=f"{role}{counter['n']}@test.local", role=role)
        return user, _token_for(user)

    return _factory


@pytest.fixture
def auth_headers(make_user_and_token):
    def _factory(role: str = "enqueteur"):
        _, token = make_user_and_token(role)
        return {"Authorization": f"Bearer {token}"}

    return _factory
