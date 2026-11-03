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


def test_coordinador_crea_y_lista_zonas(client, session_factory):
    h = auth_header(client, session_factory, "coord1@prueba.local", "coordinador")

    r = client.post("/api/v1/zonas-hogares/zonas", json={"nombre": "Zona 1", "descripcion": "Florencia"}, headers=h)
    assert r.status_code == 201
    zona_id = r.json()["id"]

    r = client.get("/api/v1/zonas-hogares/zonas", headers=h)
    assert r.status_code == 200
    assert any(z["id"] == zona_id for z in r.json())

    r = client.get(f"/api/v1/zonas-hogares/zonas/{zona_id}", headers=h)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Zona 1"

    r = client.put(f"/api/v1/zonas-hogares/zonas/{zona_id}", json={"descripcion": "actualizada"}, headers=h)
    assert r.status_code == 200
    assert r.json()["descripcion"] == "actualizada"


def test_crear_zona_sin_token_es_401(client):
    assert client.post("/api/v1/zonas-hogares/zonas", json={"nombre": "X"}).status_code == 401


def test_rol_incorrecto_no_puede_crear_zona(client, session_factory):
    h = auth_header(client, session_factory, "madre1@prueba.local", "madre")
    r = client.post("/api/v1/zonas-hogares/zonas", json={"nombre": "Zona negada"}, headers=h)
    assert r.status_code == 403


def test_admin_crea_hogar_y_lo_filtra_por_zona(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")

    r = client.post("/api/v1/zonas-hogares/zonas", json={"nombre": "Zona 2"}, headers=h)
    zona_id = r.json()["id"]

    r = client.post(
        "/api/v1/zonas-hogares/hogares",
        json={"zona_id": zona_id, "capacidad_maxima": 6},
        headers=h,
    )
    assert r.status_code == 201
    hogar_id = r.json()["id"]
    assert r.json()["estado"] == "activo"

    r = client.get(f"/api/v1/zonas-hogares/hogares?zona_id={zona_id}", headers=h)
    assert r.status_code == 200
    assert any(hg["id"] == hogar_id for hg in r.json())

    r = client.put(f"/api/v1/zonas-hogares/hogares/{hogar_id}", json={"estado": "suspendido"}, headers=h)
    assert r.status_code == 200
    assert r.json()["estado"] == "suspendido"


def test_capacidad_invalida_es_422(client, session_factory):
    h = auth_header(client, session_factory, "coord2@prueba.local", "coordinador")
    r = client.post("/api/v1/zonas-hogares/zonas", json={"nombre": "Zona 3"}, headers=h)
    zona_id = r.json()["id"]

    r = client.post(
        "/api/v1/zonas-hogares/hogares",
        json={"zona_id": zona_id, "capacidad_maxima": 50},
        headers=h,
    )
    assert r.status_code == 422
