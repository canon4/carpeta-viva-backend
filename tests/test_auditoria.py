from app.core.security import hash_password
from app.modules.auth.models import Usuario

from .conftest import CLAVE_SINTETICA


def crear_usuario(session_factory, email, rol):
    with session_factory() as s:
        s.add(Usuario(email=email, password_hash=hash_password(CLAVE_SINTETICA), rol=rol))
        s.commit()


def login(client, email, password=CLAVE_SINTETICA):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


def auth_header(client, session_factory, email, rol):
    crear_usuario(session_factory, email, rol)
    token = login(client, email)
    return {"Authorization": f"Bearer {token}"}


def test_auditor_lista_accesos(client, session_factory):
    h = auth_header(client, session_factory, "auditor1@prueba.local", "auditor")

    # El propio login (fallido y exitoso) ya queda auditado.
    client.post("/api/v1/auth/login", json={"email": "defensor@prueba.local", "password": "mala"})

    r = client.get("/api/v1/auditoria", headers=h)
    assert r.status_code == 200
    acciones = [a["accion"] for a in r.json()]
    assert "login_fallido" in acciones
    assert "login_ok" in acciones


def test_auditoria_filtra_por_accion_y_pagina(client, session_factory):
    h = auth_header(client, session_factory, "auditor2@prueba.local", "auditor")

    r = client.get("/api/v1/auditoria?accion=login_ok&limit=1&offset=0", headers=h)
    assert r.status_code == 200
    assert all(a["accion"] == "login_ok" for a in r.json())
    assert len(r.json()) <= 1


def test_auditoria_sin_token_es_401(client):
    assert client.get("/api/v1/auditoria").status_code == 401


def test_rol_incorrecto_no_ve_auditoria(client, session_factory):
    h = auth_header(client, session_factory, "coord1@prueba.local", "coordinador")
    assert client.get("/api/v1/auditoria", headers=h).status_code == 403
