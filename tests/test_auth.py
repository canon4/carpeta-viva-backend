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


def test_login_pone_cookie_httponly_de_refresco(client):
    r = login(client)
    cookie = r.cookies.get("refresh_token")
    assert cookie
    # La cookie solo debe viajar en /api/v1/auth/*, nunca exponerse en el cuerpo JSON.
    assert "refresh_token" not in r.json()


def test_refrescar_sin_cookie_es_401(client):
    assert client.post("/api/v1/auth/refrescar").status_code == 401


def test_refrescar_con_cookie_da_access_token_nuevo_sin_contrasena(client):
    login(client)
    r2 = client.post("/api/v1/auth/refrescar")
    assert r2.status_code == 200
    assert r2.json()["access_token"]
    assert r2.json()["token_type"] == "bearer"


def test_access_token_no_sirve_como_cookie_de_refresco(client, token):
    client.cookies.set("refresh_token", token)
    r = client.post("/api/v1/auth/refrescar")
    assert r.status_code == 401


def test_refrescar_tras_bloquear_usuario_falla(client, session_factory):
    login(client)
    with session_factory() as s:
        from app.modules.auth.models import Usuario

        usuario = s.scalar(select(Usuario).where(Usuario.email == "defensor@prueba.local"))
        usuario.activo = False
        s.add(usuario)
        s.commit()
    assert client.post("/api/v1/auth/refrescar").status_code == 401


def test_logout_borra_la_cookie(client):
    login(client)
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    assert client.post("/api/v1/auth/refrescar").status_code == 401


def test_cambiar_contrasena_renueva_la_cookie_de_refresco(client, token):
    r = client.put(
        "/api/v1/auth/contrasena",
        json={"actual": CLAVE_SINTETICA, "nueva": "otra-clave-larga-123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert client.post("/api/v1/auth/refrescar").status_code == 200


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
