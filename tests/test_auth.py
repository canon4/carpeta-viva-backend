from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.deps import requiere_roles
from app.modules.auditoria.models import AuditoriaAcceso
from app.modules.auth.domain import Rol

from .conftest import CLAVE_SINTETICA


def login(client, email="defensor@prueba.local", password=CLAVE_SINTETICA):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_login_correcto_devuelve_token(client):
    r = login(client)
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_ignora_mayusculas_en_el_correo(client):
    assert login(client, email="DEFENSOR@prueba.local").status_code == 200


def test_clave_incorrecta_es_401(client):
    assert login(client, password="otra").status_code == 401


def test_usuario_inexistente_es_401(client):
    assert login(client, email="nadie@prueba.local").status_code == 401


def test_usuario_inactivo_no_entra(client):
    assert login(client, email="inactivo@prueba.local").status_code == 401


def test_me_con_token(client, token):
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "defensor@prueba.local"
    assert r.json()["rol"] == "defensor"
    assert "password_hash" not in r.json()


def test_me_sin_token_es_401(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_con_token_basura_es_401(client):
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_login_queda_auditado(client, session_factory):
    login(client)
    login(client, password="mala")
    with session_factory() as s:
        acciones = [a.accion for a in s.scalars(select(AuditoriaAcceso))]
    assert sorted(acciones) == ["login_fallido", "login_ok"]


def test_guardia_de_roles(app, token):
    @app.get("/solo-coordinador")
    def solo_coordinador(_=Depends(requiere_roles(Rol.COORDINADOR))):
        return {"ok": True}

    @app.get("/solo-defensor")
    def solo_defensor(_=Depends(requiere_roles(Rol.DEFENSOR))):
        return {"ok": True}

    cliente = TestClient(app)
    h = {"Authorization": f"Bearer {token}"}
    assert cliente.get("/solo-coordinador", headers=h).status_code == 403
    assert cliente.get("/solo-defensor", headers=h).status_code == 200
