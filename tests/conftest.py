import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import models  # noqa: F401  (registra todas las tablas)
from app.core.database import Base, get_session
from app.core.security import hash_password
from app.main import create_app
from app.modules.auth.models import Usuario

CLAVE_SINTETICA = "clave-sintetica-123"


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def app(session_factory):
    aplicacion = create_app()

    def _sesion():
        with session_factory() as s:
            yield s

    aplicacion.dependency_overrides[get_session] = _sesion
    with session_factory() as s:
        s.add(Usuario(email="defensor@prueba.local", password_hash=hash_password(CLAVE_SINTETICA), rol="defensor"))
        s.add(
            Usuario(
                email="inactivo@prueba.local",
                password_hash=hash_password(CLAVE_SINTETICA),
                rol="madre",
                activo=False,
            )
        )
        s.commit()
    return aplicacion


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def token(client):
    r = client.post("/api/v1/auth/login", json={"email": "defensor@prueba.local", "password": CLAVE_SINTETICA})
    return r.json()["access_token"]
