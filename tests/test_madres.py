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


def crear_madre(client, h, numero_identificacion="100", usuario_id=None):
    payload = {
        "nombres": "Ana",
        "apellidos": "Pérez",
        "numero_identificacion": numero_identificacion,
    }
    if usuario_id is not None:
        payload["usuario_id"] = usuario_id
    return client.post("/api/v1/madres", json=payload, headers=h)


def test_coordinador_crea_lista_y_actualiza_madre(client, session_factory):
    h = auth_header(client, session_factory, "coord1@prueba.local", "coordinador")

    r = crear_madre(client, h, "100")
    assert r.status_code == 201
    madre_id = r.json()["id"]
    assert r.json()["estado_certificacion"] == "pendiente"

    r = client.get("/api/v1/madres", headers=h)
    assert r.status_code == 200
    assert any(m["id"] == madre_id for m in r.json())

    r = client.get(f"/api/v1/madres/{madre_id}", headers=h)
    assert r.status_code == 200

    r = client.put(f"/api/v1/madres/{madre_id}", json={"estado_certificacion": "vigente"}, headers=h)
    assert r.status_code == 200
    assert r.json()["estado_certificacion"] == "vigente"


def test_crear_madre_sin_token_es_401(client):
    assert crear_madre(client, {}, "101").status_code == 401


def test_rol_incorrecto_no_puede_crear_madre(client, session_factory):
    h = auth_header(client, session_factory, "profesional1@prueba.local", "profesional")
    assert crear_madre(client, h, "102").status_code == 403


def test_madre_ve_su_propio_perfil_y_carga_firma(client, session_factory):
    with session_factory() as s:
        usuario = Usuario(email="madre1@prueba.local", password_hash=hash_password(CLAVE_SINTETICA), rol="madre")
        s.add(usuario)
        s.commit()
        usuario_id = str(usuario.id)

    h_coord = auth_header(client, session_factory, "coord2@prueba.local", "coordinador")
    r = crear_madre(client, h_coord, "103", usuario_id=usuario_id)
    assert r.status_code == 201

    token = login(client, "madre1@prueba.local")
    h_madre = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/madres/yo", headers=h_madre)
    assert r.status_code == 200
    assert r.json()["numero_identificacion"] == "103"
    assert r.json()["hogar_id"] is None  # sin hogar asignado todavía

    r = client.put("/api/v1/madres/yo/firma", json={"firma_ref": "firma-demo-123"}, headers=h_madre)
    assert r.status_code == 200
    assert r.json()["firma_ref"] == "firma-demo-123"


def test_madre_yo_incluye_su_hogar_sin_pasar_por_zonas_hogares(client, session_factory):
    """La madre no tiene acceso a Zonas y Hogares (roles coordinador/admin); /madres/yo le dice
    el id de su propio hogar para que pueda usar Inventario, Alimentos y el Asistente de IA."""
    with session_factory() as s:
        usuario = Usuario(email="madre3@prueba.local", password_hash=hash_password(CLAVE_SINTETICA), rol="madre")
        s.add(usuario)
        s.commit()
        usuario_id = str(usuario.id)

    h_coord = auth_header(client, session_factory, "coord3@prueba.local", "coordinador")
    r = crear_madre(client, h_coord, "104", usuario_id=usuario_id)
    madre_id = r.json()["id"]

    r = client.post("/api/v1/zonas-hogares/zonas", json={"nombre": "Zona Prueba"}, headers=h_coord)
    zona_id = r.json()["id"]
    r = client.post("/api/v1/zonas-hogares/hogares", json={"zona_id": zona_id}, headers=h_coord)
    hogar_id = r.json()["id"]
    r = client.put(f"/api/v1/zonas-hogares/hogares/{hogar_id}", json={"madre_id": madre_id}, headers=h_coord)
    assert r.status_code == 200

    token = login(client, "madre3@prueba.local")
    h_madre = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/madres/yo", headers=h_madre)
    assert r.status_code == 200
    assert r.json()["hogar_id"] == hogar_id

    # La madre sigue sin poder listar Zonas y Hogares directamente.
    assert client.get("/api/v1/zonas-hogares/hogares", headers=h_madre).status_code == 403


def test_madre_sin_perfil_asociado_es_404(client, session_factory):
    h = auth_header(client, session_factory, "madre2@prueba.local", "madre")
    r = client.get("/api/v1/madres/yo", headers=h)
    assert r.status_code == 404
