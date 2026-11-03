"""Pruebas de Control de Alimentos (ADR-0009, sección 4): CRUD por hogar, autorización
mediante `puede_ver_hogar`/`puede_gestionar_hogar`, filtro de vencidos y que "eliminar" solo
marca `consumido` en vez de borrar físico.
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
    "nombres": "Mateo Prueba",
    "apellidos": "Sintético",
    "fecha_nacimiento": "2015-03-01",
}


def crear_menor(client, h):
    return client.post("/api/v1/menores", json=MENOR_SINTETICO, headers=h).json()["id"]


def ingresar_menor(client, h_admin, menor_id, hogar_id):
    return client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )


def test_madre_del_hogar_crea_y_lista_alimento(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ali1")
    uid_madre = crear_usuario(session_factory, "madre_ali1@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "ali-1")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_ali1@prueba.local')}"}

    r = client.post(
        "/api/v1/alimentos",
        json={
            "hogar_id": hogar_id,
            "descripcion": "Arroz",
            "fecha_ingreso": "2026-01-01",
            "perecedero": False,
            "cantidad": 10,
            "unidad": "kg",
        },
        headers=h_madre,
    )
    assert r.status_code == 201
    assert r.json()["consumido"] is False
    item_id = r.json()["id"]

    r = client.get(f"/api/v1/alimentos?hogar_id={hogar_id}", headers=h_madre)
    assert r.status_code == 200
    assert any(i["id"] == item_id for i in r.json())


def test_fecha_vencimiento_sin_perecedero_es_422(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ali2")
    h_admin = auth_header(client, session_factory, "admin_ali2@prueba.local", "admin")

    r = client.post(
        "/api/v1/alimentos",
        json={
            "hogar_id": hogar_id,
            "descripcion": "Leche",
            "fecha_ingreso": "2026-01-01",
            "perecedero": False,
            "fecha_vencimiento": "2026-02-01",
            "cantidad": 5,
        },
        headers=h_admin,
    )
    assert r.status_code == 422


def test_filtro_vencidos(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ali3")
    h_admin = auth_header(client, session_factory, "admin_ali3@prueba.local", "admin")

    r_vencido = client.post(
        "/api/v1/alimentos",
        json={
            "hogar_id": hogar_id,
            "descripcion": "Yogurt",
            "fecha_ingreso": "2026-01-01",
            "perecedero": True,
            "fecha_vencimiento": "2020-01-01",
            "cantidad": 2,
        },
        headers=h_admin,
    )
    assert r_vencido.status_code == 201

    r_vigente = client.post(
        "/api/v1/alimentos",
        json={
            "hogar_id": hogar_id,
            "descripcion": "Queso",
            "fecha_ingreso": "2026-01-01",
            "perecedero": True,
            "fecha_vencimiento": "2099-01-01",
            "cantidad": 1,
        },
        headers=h_admin,
    )
    assert r_vigente.status_code == 201

    r = client.get(f"/api/v1/alimentos?hogar_id={hogar_id}&vencidos=true", headers=h_admin)
    assert r.status_code == 200
    descripciones = {i["descripcion"] for i in r.json()}
    assert descripciones == {"Yogurt"}


def test_marcar_consumido_no_borra(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ali4")
    h_admin = auth_header(client, session_factory, "admin_ali4@prueba.local", "admin")

    r = client.post(
        "/api/v1/alimentos",
        json={
            "hogar_id": hogar_id,
            "descripcion": "Pan",
            "fecha_ingreso": "2026-01-01",
            "perecedero": True,
            "fecha_vencimiento": "2026-01-05",
            "cantidad": 3,
        },
        headers=h_admin,
    )
    item_id = r.json()["id"]

    r = client.put(f"/api/v1/alimentos/{item_id}/consumido", headers=h_admin)
    assert r.status_code == 200
    assert r.json()["consumido"] is True

    r = client.get(f"/api/v1/alimentos?hogar_id={hogar_id}", headers=h_admin)
    assert any(i["id"] == item_id and i["consumido"] is True for i in r.json())


def test_madre_de_otro_hogar_no_puede_gestionar(client, session_factory):
    _, hogar_id = crear_zona_y_hogar(session_factory, "Zona ali5")
    _, hogar_ajeno = crear_zona_y_hogar(session_factory, "Zona ali5-ajena")

    uid_madre = crear_usuario(session_factory, "madre_ali5@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "ali-5")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_ali5@prueba.local')}"}

    r = client.post(
        "/api/v1/alimentos",
        json={
            "hogar_id": hogar_ajeno,
            "descripcion": "Azúcar",
            "fecha_ingreso": "2026-01-01",
            "perecedero": False,
            "cantidad": 2,
        },
        headers=h_madre,
    )
    assert r.status_code == 403


def test_coordinador_de_otra_zona_no_lista(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ali6")
    h_admin = auth_header(client, session_factory, "admin_ali6@prueba.local", "admin")
    client.post(
        "/api/v1/alimentos",
        json={
            "hogar_id": hogar_id,
            "descripcion": "Sal",
            "fecha_ingreso": "2026-01-01",
            "perecedero": False,
            "cantidad": 1,
        },
        headers=h_admin,
    )

    h_coord_otra = auth_header(client, session_factory, "coord_ali6@prueba.local", "coordinador")
    r = client.get(f"/api/v1/alimentos?hogar_id={hogar_id}", headers=h_coord_otra)
    assert r.status_code == 403


def test_profesional_con_menor_en_el_hogar_puede_gestionar(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ali7")
    h_admin = auth_header(client, session_factory, "admin_ali7@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_defensor = crear_usuario(session_factory, "defensor_ali7@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_defensor, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    h_defensor = {"Authorization": f"Bearer {login(client, 'defensor_ali7@prueba.local')}"}

    r = client.post(
        "/api/v1/alimentos",
        json={
            "hogar_id": hogar_id,
            "descripcion": "Huevos",
            "fecha_ingreso": "2026-01-01",
            "perecedero": True,
            "fecha_vencimiento": "2026-02-01",
            "cantidad": 12,
            "unidad": "unidades",
        },
        headers=h_defensor,
    )
    assert r.status_code == 201


def test_profesional_sin_relacion_no_puede_gestionar(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ali8")
    h_admin = auth_header(client, session_factory, "admin_ali8@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_psico = crear_usuario(session_factory, "psico_ali8@prueba.local", "profesional")
    crear_profesional(session_factory, uid_psico, "psicosocial")
    h_psico = {"Authorization": f"Bearer {login(client, 'psico_ali8@prueba.local')}"}

    r = client.post(
        "/api/v1/alimentos",
        json={
            "hogar_id": hogar_id,
            "descripcion": "Papa",
            "fecha_ingreso": "2026-01-01",
            "perecedero": True,
            "fecha_vencimiento": "2026-02-01",
            "cantidad": 5,
        },
        headers=h_psico,
    )
    assert r.status_code == 403


def test_auditor_solo_ve_pero_no_gestiona(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ali9")
    h_admin = auth_header(client, session_factory, "admin_ali9@prueba.local", "admin")
    client.post(
        "/api/v1/alimentos",
        json={
            "hogar_id": hogar_id,
            "descripcion": "Lentejas",
            "fecha_ingreso": "2026-01-01",
            "perecedero": False,
            "cantidad": 2,
        },
        headers=h_admin,
    )
    h_auditor = auth_header(client, session_factory, "auditor_ali9@prueba.local", "auditor")

    r = client.get(f"/api/v1/alimentos?hogar_id={hogar_id}", headers=h_auditor)
    assert r.status_code == 200

    r = client.post(
        "/api/v1/alimentos",
        json={
            "hogar_id": hogar_id,
            "descripcion": "Café",
            "fecha_ingreso": "2026-01-01",
            "perecedero": False,
            "cantidad": 1,
        },
        headers=h_auditor,
    )
    assert r.status_code == 403


def test_sin_token_es_401(client):
    assert client.get("/api/v1/alimentos?hogar_id=00000000-0000-0000-0000-000000000000").status_code == 401
