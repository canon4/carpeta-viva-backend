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


def crear_profesional(client, h, cargo="psicosocial"):
    return client.post(
        "/api/v1/profesionales",
        json={"nombres": "Luis", "apellidos": "Gómez", "cargo": cargo},
        headers=h,
    )


def test_coordinador_crea_lista_filtra_y_actualiza_profesional(client, session_factory):
    h = auth_header(client, session_factory, "coord1@prueba.local", "coordinador")

    r = crear_profesional(client, h, "psicosocial")
    assert r.status_code == 201
    profesional_id = r.json()["id"]

    r2 = crear_profesional(client, h, "nutricion")
    assert r2.status_code == 201

    r = client.get("/api/v1/profesionales", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 2

    r = client.get("/api/v1/profesionales?cargo=nutricion", headers=h)
    assert r.status_code == 200
    assert all(p["cargo"] == "nutricion" for p in r.json())

    r = client.get(f"/api/v1/profesionales/{profesional_id}", headers=h)
    assert r.status_code == 200

    r = client.put(f"/api/v1/profesionales/{profesional_id}", json={"especialidad": "Psicología clínica"}, headers=h)
    assert r.status_code == 200
    assert r.json()["especialidad"] == "Psicología clínica"


def test_crear_profesional_sin_token_es_401(client):
    assert crear_profesional(client, {}).status_code == 401


def test_rol_incorrecto_no_puede_crear_profesional(client, session_factory):
    h = auth_header(client, session_factory, "defensor1@prueba.local", "defensor")
    assert crear_profesional(client, h).status_code == 403
