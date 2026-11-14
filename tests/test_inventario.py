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


# ---------------------------------------------------------------------------
# Pedido y recepción (ADR-0014)
# ---------------------------------------------------------------------------

def test_coordinador_crea_pedido_no_recibido(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ped1")
    h_coord = auth_header(client, session_factory, "coord_ped1@prueba.local", "coordinador", zona_id)

    r = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama nueva", "cantidad": 5, "estado": "malo"},
        headers=h_coord,
    )
    assert r.status_code == 201
    datos = r.json()
    assert datos["recibido"] is False
    # El `estado` que mande el coordinador se ignora en la creación: no existe nada físico aún.
    assert datos["estado"] == "bueno"


def test_madre_crea_directo_recibido(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ped2")
    uid_madre = crear_usuario(session_factory, "madre_ped2@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "ped-2")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_ped2@prueba.local')}"}

    r = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "mueble", "descripcion": "Armario", "cantidad": 1, "estado": "bueno"},
        headers=h_madre,
    )
    assert r.status_code == 201
    assert r.json()["recibido"] is True


def test_coordinador_no_puede_confirmar_recepcion(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ped3")
    h_coord = auth_header(client, session_factory, "coord_ped3@prueba.local", "coordinador", zona_id)
    item_id = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama", "cantidad": 1},
        headers=h_coord,
    ).json()["id"]

    r = client.put(f"/api/v1/inventario/items/{item_id}/recepcion", json={"estado": "bueno"}, headers=h_coord)
    assert r.status_code == 403


def test_madre_confirma_recepcion_de_pedido_del_coordinador(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ped4")
    h_coord = auth_header(client, session_factory, "coord_ped4@prueba.local", "coordinador", zona_id)
    item_id = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama", "cantidad": 3},
        headers=h_coord,
    ).json()["id"]

    uid_madre = crear_usuario(session_factory, "madre_ped4@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "ped-4")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_ped4@prueba.local')}"}

    r = client.put(f"/api/v1/inventario/items/{item_id}/recepcion", json={"estado": "regular"}, headers=h_madre)
    assert r.status_code == 200
    assert r.json()["recibido"] is True
    assert r.json()["estado"] == "regular"


def test_confirmar_recepcion_dos_veces_es_422(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ped5")
    h_admin = auth_header(client, session_factory, "admin_ped5@prueba.local", "admin")
    item_id = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama", "cantidad": 1, "estado": "bueno"},
        headers=h_admin,
    ).json()["id"]
    # El admin ya la crea `recibido=true`; confirmar de nuevo debe rechazarse.
    r = client.put(f"/api/v1/inventario/items/{item_id}/recepcion", json={"estado": "bueno"}, headers=h_admin)
    assert r.status_code == 422


def test_coordinador_no_edita_tipo_cantidad_de_item_recibido(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ped6")
    h_coord = auth_header(client, session_factory, "coord_ped6@prueba.local", "coordinador", zona_id)
    item_id = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama", "cantidad": 2},
        headers=h_coord,
    ).json()["id"]

    uid_madre = crear_usuario(session_factory, "madre_ped6@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "ped-6")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_ped6@prueba.local')}"}
    r = client.put(f"/api/v1/inventario/items/{item_id}/recepcion", json={"estado": "bueno"}, headers=h_madre)
    assert r.status_code == 200

    r = client.put(f"/api/v1/inventario/items/{item_id}", json={"cantidad": 4}, headers=h_coord)
    assert r.status_code == 422


def test_madre_no_puede_editar_pedido_ajeno(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona ped7")
    h_coord = auth_header(client, session_factory, "coord_ped7@prueba.local", "coordinador", zona_id)
    item_id = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama", "cantidad": 2},
        headers=h_coord,
    ).json()["id"]

    uid_madre = crear_usuario(session_factory, "madre_ped7@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "ped-7")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_ped7@prueba.local')}"}

    r = client.put(f"/api/v1/inventario/items/{item_id}", json={"cantidad": 10}, headers=h_madre)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Fotos de evidencia (ADR-0014, sección 2)
# ---------------------------------------------------------------------------

def _item_recibido_de_madre(client, session_factory, zona_nombre, email_madre, numero_doc):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, zona_nombre)
    uid_madre = crear_usuario(session_factory, email_madre, "madre")
    madre_id = crear_madre(session_factory, uid_madre, numero_doc)
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, email_madre)}"}
    item_id = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama", "cantidad": 1},
        headers=h_madre,
    ).json()["id"]
    return hogar_id, item_id, h_madre


def test_subir_foto_valida(client, session_factory):
    hogar_id, item_id, h_madre = _item_recibido_de_madre(client, session_factory, "Zona foto1", "madre_foto1@prueba.local", "foto-1")

    r = client.post(
        f"/api/v1/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia.jpg", b"contenido-sintetico", "image/jpeg")},
        data={"declaracion_sin_menores": "true"},
        headers=h_madre,
    )
    assert r.status_code == 201
    assert r.json()["mime_type"] == "image/jpeg"
    assert r.json()["declaracion_sin_menores"] is True
    assert r.json()["oculta"] is False


def test_subir_foto_tipo_invalido_es_422(client, session_factory):
    hogar_id, item_id, h_madre = _item_recibido_de_madre(client, session_factory, "Zona foto2", "madre_foto2@prueba.local", "foto-2")

    r = client.post(
        f"/api/v1/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia.pdf", b"contenido-sintetico", "application/pdf")},
        data={"declaracion_sin_menores": "true"},
        headers=h_madre,
    )
    assert r.status_code == 422


def test_subir_foto_excede_tamanio_es_422(client, session_factory):
    hogar_id, item_id, h_madre = _item_recibido_de_madre(client, session_factory, "Zona foto3", "madre_foto3@prueba.local", "foto-3")

    contenido_grande = b"a" * (5 * 1024 * 1024 + 1)
    r = client.post(
        f"/api/v1/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia.jpg", contenido_grande, "image/jpeg")},
        data={"declaracion_sin_menores": "true"},
        headers=h_madre,
    )
    assert r.status_code == 422


def test_subir_mas_de_6_fotos_es_422(client, session_factory):
    hogar_id, item_id, h_madre = _item_recibido_de_madre(client, session_factory, "Zona foto4", "madre_foto4@prueba.local", "foto-4")

    for i in range(6):
        r = client.post(
            f"/api/v1/inventario/items/{item_id}/fotos",
            files={"archivo": (f"evidencia{i}.jpg", b"contenido-sintetico", "image/jpeg")},
            data={"declaracion_sin_menores": "true"},
            headers=h_madre,
        )
        assert r.status_code == 201

    r = client.post(
        f"/api/v1/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia7.jpg", b"contenido-sintetico", "image/jpeg")},
        data={"declaracion_sin_menores": "true"},
        headers=h_madre,
    )
    assert r.status_code == 422


def test_coordinador_no_puede_subir_foto(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona foto5")
    h_coord = auth_header(client, session_factory, "coord_foto5@prueba.local", "coordinador", zona_id)
    item_id = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama", "cantidad": 1},
        headers=h_coord,
    ).json()["id"]

    r = client.post(
        f"/api/v1/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia.jpg", b"contenido-sintetico", "image/jpeg")},
        data={"declaracion_sin_menores": "true"},
        headers=h_coord,
    )
    assert r.status_code == 403


def test_subir_foto_sin_declaracion_es_422(client, session_factory):
    hogar_id, item_id, h_madre = _item_recibido_de_madre(
        client, session_factory, "Zona foto7", "madre_foto7@prueba.local", "foto-7"
    )

    r = client.post(
        f"/api/v1/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia.jpg", b"contenido-sintetico", "image/jpeg")},
        headers=h_madre,
    )
    assert r.status_code == 422


def test_subir_foto_con_declaracion_false_es_422(client, session_factory):
    hogar_id, item_id, h_madre = _item_recibido_de_madre(
        client, session_factory, "Zona foto8", "madre_foto8@prueba.local", "foto-8"
    )

    r = client.post(
        f"/api/v1/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia.jpg", b"contenido-sintetico", "image/jpeg")},
        data={"declaracion_sin_menores": "false"},
        headers=h_madre,
    )
    assert r.status_code == 422


def test_lectura_de_fotos_restringida_a_madre_admin_auditor(client, session_factory):
    hogar_id, item_id, h_madre = _item_recibido_de_madre(client, session_factory, "Zona foto6", "madre_foto6@prueba.local", "foto-6")
    client.post(
        f"/api/v1/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia.jpg", b"contenido-sintetico", "image/jpeg")},
        data={"declaracion_sin_menores": "true"},
        headers=h_madre,
    )
    foto_id = client.get(f"/api/v1/inventario/items/{item_id}/fotos", headers=h_madre).json()[0]["id"]

    r = client.get(f"/api/v1/inventario/items/{item_id}/fotos", headers=h_madre)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get(f"/api/v1/inventario/items/{item_id}/fotos/{foto_id}", headers=h_madre)
    assert r.status_code == 200
    assert r.content == b"contenido-sintetico"

    h_auditor = auth_header(client, session_factory, "auditor_foto6@prueba.local", "auditor")
    r = client.get(f"/api/v1/inventario/items/{item_id}/fotos", headers=h_auditor)
    assert r.status_code == 200
    r = client.get(f"/api/v1/inventario/items/{item_id}/fotos/{foto_id}", headers=h_auditor)
    assert r.status_code == 200


def test_coordinador_profesional_defensor_no_leen_fotos(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona foto9")
    h_admin = auth_header(client, session_factory, "admin_foto9@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_madre = crear_usuario(session_factory, "madre_foto9@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "foto-9")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_foto9@prueba.local')}"}
    item_id = client.post(
        "/api/v1/inventario/items",
        json={"hogar_id": hogar_id, "tipo": "cama", "descripcion": "Cama", "cantidad": 1},
        headers=h_madre,
    ).json()["id"]
    foto_id = client.post(
        f"/api/v1/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia.jpg", b"contenido-sintetico", "image/jpeg")},
        data={"declaracion_sin_menores": "true"},
        headers=h_madre,
    ).json()["id"]

    h_coord = auth_header(client, session_factory, "coord_foto9@prueba.local", "coordinador", zona_id)
    assert client.get(f"/api/v1/inventario/items/{item_id}/fotos", headers=h_coord).status_code == 403
    assert client.get(f"/api/v1/inventario/items/{item_id}/fotos/{foto_id}", headers=h_coord).status_code == 403

    uid_defensor = crear_usuario(session_factory, "defensor_foto9@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_defensor, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    h_defensor = {"Authorization": f"Bearer {login(client, 'defensor_foto9@prueba.local')}"}
    assert client.get(f"/api/v1/inventario/items/{item_id}/fotos", headers=h_defensor).status_code == 403
    assert client.get(f"/api/v1/inventario/items/{item_id}/fotos/{foto_id}", headers=h_defensor).status_code == 403


def test_admin_oculta_foto_y_deja_de_verla_la_madre(client, session_factory):
    hogar_id, item_id, h_madre = _item_recibido_de_madre(
        client, session_factory, "Zona foto10", "madre_foto10@prueba.local", "foto-10"
    )
    foto_id = client.post(
        f"/api/v1/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia.jpg", b"contenido-sintetico", "image/jpeg")},
        data={"declaracion_sin_menores": "true"},
        headers=h_madre,
    ).json()["id"]

    h_admin = auth_header(client, session_factory, "admin_foto10@prueba.local", "admin")
    r = client.put(
        f"/api/v1/inventario/items/{item_id}/fotos/{foto_id}/ocultar",
        headers=h_admin,
    )
    assert r.status_code == 200
    assert r.json()["oculta"] is True

    r = client.get(f"/api/v1/inventario/items/{item_id}/fotos", headers=h_madre)
    assert r.status_code == 200
    assert r.json() == []
    r = client.get(f"/api/v1/inventario/items/{item_id}/fotos/{foto_id}", headers=h_madre)
    assert r.status_code == 404

    r = client.get(f"/api/v1/inventario/items/{item_id}/fotos", headers=h_admin)
    assert r.status_code == 200
    assert len(r.json()) == 1
    r = client.get(f"/api/v1/inventario/items/{item_id}/fotos/{foto_id}", headers=h_admin)
    assert r.status_code == 200


def test_no_admin_no_puede_ocultar_foto(client, session_factory):
    hogar_id, item_id, h_madre = _item_recibido_de_madre(
        client, session_factory, "Zona foto11", "madre_foto11@prueba.local", "foto-11"
    )
    foto_id = client.post(
        f"/api/v1/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia.jpg", b"contenido-sintetico", "image/jpeg")},
        data={"declaracion_sin_menores": "true"},
        headers=h_madre,
    ).json()["id"]

    r = client.put(
        f"/api/v1/inventario/items/{item_id}/fotos/{foto_id}/ocultar",
        headers=h_madre,
    )
    assert r.status_code == 403
