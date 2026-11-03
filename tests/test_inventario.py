"""Pruebas de Inventario del Hogar (ADR-0009, sección 3): CRUD por hogar, autorización
mediante `puede_ver_hogar`/`puede_gestionar_hogar`, y que "eliminar" solo desactiva/marca
estado en vez de borrar físico.
"""
from ._helpers import (
    asignar_profesional_a_menor,
    auth_header,
    crear_madre,
    crear_profesional,
    crear_usuario,
    crear_zona_y_hogar,
    login,
    vincular_hogar_madre,
)

MENOR_SINTETICO = {
    "nombres": "Luisa Prueba",
    "apellidos": "Sintética",
    "fecha_nacimiento": "2016-05-10",
}


def crear_menor(client, h):
    return client.post("/api/v1/menores", json=MENOR_SINTETICO, headers=h).json()["id"]


def ingresar_menor(client, h_admin, menor_id, hogar_id):
    return client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )


# ---------------------------------------------------------------------------
# Items de inventario
# ---------------------------------------------------------------------------

def test_madre_del_hogar_crea_y_lista_item(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    uid_madre = crear_usuario(session_factory, "madre_inv1@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "inv-1")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_inv1@prueba.local')}"}

    r = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama sencilla", "cantidad": 2},
        headers=h_madre,
    )
    assert r.status_code == 201
    assert r.json()["estado"] == "bueno"
    item_id = r.json()["id"]

    r = client.get(f"/api/v1/inventario/items?hogar_id={hogar_id}", headers=h_madre)
    assert r.status_code == 200
    assert any(i["id"] == item_id for i in r.json())


def test_madre_de_otro_hogar_no_puede_crear_item(client, session_factory):
    _, hogar_id = crear_zona_y_hogar(session_factory, "Zona inv2")
    _, hogar_ajeno = crear_zona_y_hogar(session_factory, "Zona inv2-ajena")

    uid_madre = crear_usuario(session_factory, "madre_inv2@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "inv-2")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_inv2@prueba.local')}"}

    r = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_ajeno, "tipo": "mueble", "descripcion": "Armario", "cantidad": 1},
        headers=h_madre,
    )
    assert r.status_code == 403


def test_coordinador_de_otra_zona_no_lista_items(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona inv3")
    h_admin = auth_header(client, session_factory, "admin_inv3@prueba.local", "admin")
    client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "otro", "descripcion": "Nevera", "cantidad": 1},
        headers=h_admin,
    )

    h_coord_otra = auth_header(client, session_factory, "coord_inv3@prueba.local", "coordinador")
    r = client.get(f"/api/v1/inventario/items?hogar_id={hogar_id}", headers=h_coord_otra)
    assert r.status_code == 403


def test_coordinador_de_la_zona_si_lista_items(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona inv4")
    h_admin = auth_header(client, session_factory, "admin_inv4@prueba.local", "admin")
    client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "otro", "descripcion": "Estufa", "cantidad": 1},
        headers=h_admin,
    )

    h_coord = auth_header(client, session_factory, "coord_inv4@prueba.local", "coordinador", zona_id)
    r = client.get(f"/api/v1/inventario/items?hogar_id={hogar_id}", headers=h_coord)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_profesional_con_menor_en_el_hogar_puede_gestionar(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona inv5")
    h_admin = auth_header(client, session_factory, "admin_inv5@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_defensor = crear_usuario(session_factory, "defensor_inv5@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_defensor, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    h_defensor = {"Authorization": f"Bearer {login(client, 'defensor_inv5@prueba.local')}"}

    r = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama litera", "cantidad": 1},
        headers=h_defensor,
    )
    assert r.status_code == 201


def test_profesional_sin_relacion_no_puede_gestionar(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona inv6")
    h_admin = auth_header(client, session_factory, "admin_inv6@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_psico = crear_usuario(session_factory, "psico_inv6@prueba.local", "profesional")
    crear_profesional(session_factory, uid_psico, "psicosocial")
    h_psico = {"Authorization": f"Bearer {login(client, 'psico_inv6@prueba.local')}"}

    r = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama", "cantidad": 1},
        headers=h_psico,
    )
    assert r.status_code == 403


def test_actualizar_item_retira_en_vez_de_borrar(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona inv7")
    h_admin = auth_header(client, session_factory, "admin_inv7@prueba.local", "admin")
    r = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "mueble", "descripcion": "Silla", "cantidad": 4},
        headers=h_admin,
    )
    item_id = r.json()["id"]

    r = client.put(f"/api/v1/inventario/items/{item_id}", json={"estado": "retirado"}, headers=h_admin)
    assert r.status_code == 200
    assert r.json()["estado"] == "retirado"

    r = client.get(f"/api/v1/inventario/items?hogar_id={hogar_id}", headers=h_admin)
    assert any(i["id"] == item_id and i["estado"] == "retirado" for i in r.json())


def test_auditor_solo_ve_pero_no_gestiona(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona inv8")
    h_admin = auth_header(client, session_factory, "admin_inv8@prueba.local", "admin")
    client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama", "cantidad": 1},
        headers=h_admin,
    )
    h_auditor = auth_header(client, session_factory, "auditor_inv8@prueba.local", "auditor")

    r = client.get(f"/api/v1/inventario/items?hogar_id={hogar_id}", headers=h_auditor)
    assert r.status_code == 200

    r = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "otro", "descripcion": "Nevera", "cantidad": 1},
        headers=h_auditor,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Convivientes
# ---------------------------------------------------------------------------

def test_crear_y_desactivar_conviviente(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona conv1")
    h_admin = auth_header(client, session_factory, "admin_conv1@prueba.local", "admin")

    r = client.post(
        "/api/v1/inventario/convivientes",
        json={"hogar_id": hogar_id, "nombres": "Carlos Convive", "relacion_con_madre": "hermano"},
        headers=h_admin,
    )
    assert r.status_code == 201
    assert r.json()["activo"] is True
    conviviente_id = r.json()["id"]

    r = client.put(f"/api/v1/inventario/convivientes/{conviviente_id}", json={"activo": False}, headers=h_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False


def test_madre_de_otro_hogar_no_lista_convivientes(client, session_factory):
    _, hogar_id = crear_zona_y_hogar(session_factory, "Zona conv2")
    _, hogar_ajeno = crear_zona_y_hogar(session_factory, "Zona conv2-ajena")

    uid_madre = crear_usuario(session_factory, "madre_conv2@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "conv-2")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_conv2@prueba.local')}"}

    r = client.get(f"/api/v1/inventario/convivientes?hogar_id={hogar_ajeno}", headers=h_madre)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Red de apoyo
# ---------------------------------------------------------------------------

def test_crear_y_desactivar_red_apoyo(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona red1")
    h_admin = auth_header(client, session_factory, "admin_red1@prueba.local", "admin")

    r = client.post(
        "/api/v1/inventario/red-apoyo",
        json={"hogar_id": hogar_id, "nombres": "Tía Apoyo", "relacion": "tía", "telefono": "3001234567"},
        headers=h_admin,
    )
    assert r.status_code == 201
    contacto_id = r.json()["id"]

    r = client.put(f"/api/v1/inventario/red-apoyo/{contacto_id}", json={"activo": False}, headers=h_admin)
    assert r.status_code == 200
    assert r.json()["activo"] is False


def test_sin_token_es_401(client):
    assert client.get("/api/v1/inventario/items?hogar_id=00000000-0000-0000-0000-000000000000").status_code == 401
