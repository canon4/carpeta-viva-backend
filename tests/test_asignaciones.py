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
    "fecha_nacimiento": "2016-03-10",
}


def crear_menor(client, h):
    return client.post("/api/v1/menores", json=MENOR_SINTETICO, headers=h)


def test_crear_ingreso_y_consultar_vigente(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    menor_id = crear_menor(client, h).json()["id"]

    r = client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["estado"] == "vigente"
    assert r.json()["tipo_movimiento"] == "ingreso"

    r = client.get(f"/api/v1/asignaciones/menor/{menor_id}/vigente", headers=h)
    assert r.status_code == 200
    assert r.json()["hogar_id"] == hogar_id


def test_ingreso_duplicado_es_422(client, session_factory):
    _, hogar_id = crear_zona_y_hogar(session_factory)
    h = auth_header(client, session_factory, "admin2@prueba.local", "admin")
    menor_id = crear_menor(client, h).json()["id"]

    payload = {"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"}
    assert client.post("/api/v1/asignaciones", json=payload, headers=h).status_code == 201
    assert client.post("/api/v1/asignaciones", json=payload, headers=h).status_code == 422


def test_traslado_cierra_anterior_y_revoca_permisos_de_madre(client, session_factory):
    zona_id, hogar_origen = crear_zona_y_hogar(session_factory, "Zona origen")
    _, hogar_destino = crear_zona_y_hogar(session_factory, "Zona destino")

    h = auth_header(client, session_factory, "admin3@prueba.local", "admin")
    menor_id = crear_menor(client, h).json()["id"]

    uid_madre = crear_usuario(session_factory, "madre1@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "800-1")
    vincular_hogar_madre(session_factory, hogar_origen, madre_id)

    r = client.post(
        "/api/v1/asignaciones",
        json={
            "menor_id": menor_id,
            "hogar_id": hogar_origen,
            "fecha_inicio": "2026-01-01",
            "tipo_movimiento": "ingreso",
        },
        headers=h,
    )
    asignacion_origen_id = r.json()["id"]

    uid_defensor = crear_usuario(session_factory, "defensor1@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_defensor, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    token_defensor = login(client, "defensor1@prueba.local")
    h_defensor = {"Authorization": f"Bearer {token_defensor}"}
    client.post(
        f"/api/v1/menores/{menor_id}/permisos",
        json={"seccion": "familia", "usuario_id": str(uid_madre)},
        headers=h_defensor,
    )

    token_madre = login(client, "madre1@prueba.local")
    h_madre = {"Authorization": f"Bearer {token_madre}"}
    assert client.get(f"/api/v1/menores/{menor_id}/familiares", headers=h_madre).status_code == 200

    r = client.post(
        "/api/v1/asignaciones",
        json={
            "menor_id": menor_id,
            "hogar_id": hogar_destino,
            "fecha_inicio": "2026-06-01",
            "tipo_movimiento": "traslado",
        },
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["estado"] == "vigente"
    assert r.json()["tipo_movimiento"] == "traslado"

    r = client.get(f"/api/v1/asignaciones/{asignacion_origen_id}", headers=h)
    assert r.json()["estado"] == "cerrada"
    assert r.json()["fecha_fin"] == "2026-06-01"

    r = client.get(f"/api/v1/asignaciones/{asignacion_origen_id}/historial", headers=h)
    assert len(r.json()) == 1
    assert r.json()[0]["estado"] == "vigente"

    # RF7: la madre saliente pierde acceso al expediente (incluida la sección que tenía habilitada).
    assert client.get(f"/api/v1/menores/{menor_id}", headers=h_madre).status_code == 403
    assert client.get(f"/api/v1/menores/{menor_id}/familiares", headers=h_madre).status_code == 403


def test_cerrar_asignacion_egresa_al_menor_y_oculta_expediente_a_la_madre(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h = auth_header(client, session_factory, "admin4@prueba.local", "admin")
    menor_id = crear_menor(client, h).json()["id"]

    uid_madre = crear_usuario(session_factory, "madre2@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "800-2")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)

    r = client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h,
    )
    asignacion_id = r.json()["id"]

    token_madre = login(client, "madre2@prueba.local")
    h_madre = {"Authorization": f"Bearer {token_madre}"}
    assert client.get(f"/api/v1/menores/{menor_id}", headers=h_madre).status_code == 200

    r = client.put(
        f"/api/v1/asignaciones/{asignacion_id}/cerrar",
        json={"motivo": "egreso por restablecimiento"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "cerrada"
    assert r.json()["tipo_movimiento"] == "egreso"

    r = client.get(f"/api/v1/menores/{menor_id}", headers=h)
    assert r.json()["estado_actual"] == "egresado"
    assert r.json()["version"] == 2

    assert client.get(f"/api/v1/menores/{menor_id}", headers=h_madre).status_code == 403


def test_profesional_no_asignado_no_puede_crear_asignacion(client, session_factory):
    _, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin5@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin).json()["id"]

    uid_psico = crear_usuario(session_factory, "psico1@prueba.local", "profesional")
    crear_profesional(session_factory, uid_psico, "psicosocial")
    token_psico = login(client, "psico1@prueba.local")
    h_psico = {"Authorization": f"Bearer {token_psico}"}

    r = client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_psico,
    )
    assert r.status_code == 403


def test_listar_asignaciones_filtra_por_zona_y_hogar(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h = auth_header(client, session_factory, "admin6@prueba.local", "admin")
    menor_id = crear_menor(client, h).json()["id"]
    client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h,
    )

    r = client.get(f"/api/v1/asignaciones?zona_id={zona_id}", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get(f"/api/v1/asignaciones?hogar_id={hogar_id}", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_crear_asignacion_sin_token_es_401(client):
    r = client.post(
        "/api/v1/asignaciones",
        json={"menor_id": "00000000-0000-0000-0000-000000000000", "hogar_id": "00000000-0000-0000-0000-000000000000", "fecha_inicio": "2026-01-01"},
    )
    assert r.status_code == 401


def test_madre_sin_relacion_no_ve_lectura_de_asignaciones_de_otro_menor(client, session_factory):
    """Regresión: los endpoints de lectura de asignaciones (listar, obtener, vigente, historial) no
    tenían ningún control de autorización por fila; cualquier usuario autenticado podía consultar
    la asignación de cualquier menor. Aquí una madre sin relación con el menor no debe ver nada."""
    _, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin10@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin).json()["id"]

    r = client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )
    asignacion_id = r.json()["id"]

    uid_madre = crear_usuario(session_factory, "madre_ajena@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "800-ajena")
    _, otro_hogar_id = crear_zona_y_hogar(session_factory, "Zona sin relación")
    vincular_hogar_madre(session_factory, otro_hogar_id, madre_id)
    token_madre = login(client, "madre_ajena@prueba.local")
    h_madre = {"Authorization": f"Bearer {token_madre}"}

    assert client.get("/api/v1/asignaciones", headers=h_madre).json() == []
    assert client.get(f"/api/v1/asignaciones/{asignacion_id}", headers=h_madre).status_code == 403
    assert client.get(f"/api/v1/asignaciones/menor/{menor_id}/vigente", headers=h_madre).status_code == 403
    assert client.get(f"/api/v1/asignaciones/{asignacion_id}/historial", headers=h_madre).status_code == 403


def test_profesional_no_asignado_no_ve_lectura_de_asignacion_ajena(client, session_factory):
    _, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin11@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin).json()["id"]

    r = client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )
    asignacion_id = r.json()["id"]

    uid_psico = crear_usuario(session_factory, "psico_ajeno@prueba.local", "profesional")
    crear_profesional(session_factory, uid_psico, "psicosocial")
    token_psico = login(client, "psico_ajeno@prueba.local")
    h_psico = {"Authorization": f"Bearer {token_psico}"}

    assert client.get("/api/v1/asignaciones", headers=h_psico).json() == []
    assert client.get(f"/api/v1/asignaciones/{asignacion_id}", headers=h_psico).status_code == 403
    assert client.get(f"/api/v1/asignaciones/menor/{menor_id}/vigente", headers=h_psico).status_code == 403
    assert client.get(f"/api/v1/asignaciones/{asignacion_id}/historial", headers=h_psico).status_code == 403


def test_coordinador_de_otra_zona_no_ve_lectura_de_asignacion_ajena(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona con el menor")
    otra_zona_id, _ = crear_zona_y_hogar(session_factory, "Zona del coordinador")
    h_admin = auth_header(client, session_factory, "admin12@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin).json()["id"]

    r = client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )
    asignacion_id = r.json()["id"]

    h_coord = auth_header(client, session_factory, "coord_otra@prueba.local", "coordinador", zona_id=otra_zona_id)

    assert client.get("/api/v1/asignaciones", headers=h_coord).json() == []
    assert client.get(f"/api/v1/asignaciones/{asignacion_id}", headers=h_coord).status_code == 403
    assert client.get(f"/api/v1/asignaciones/menor/{menor_id}/vigente", headers=h_coord).status_code == 403
    assert client.get(f"/api/v1/asignaciones/{asignacion_id}/historial", headers=h_coord).status_code == 403


def test_madre_no_ve_historial_de_asignacion_aunque_tenga_acceso_vigente(client, session_factory):
    """La madre puede ver la asignación vigente de su hogar, pero no el historial de movimientos
    (igual que `historial_menor`): ese nivel de detalle excede lo que RF7 le habilita."""
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin13@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin).json()["id"]

    uid_madre = crear_usuario(session_factory, "madre_hist@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "800-hist")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)

    r = client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )
    asignacion_id = r.json()["id"]

    token_madre = login(client, "madre_hist@prueba.local")
    h_madre = {"Authorization": f"Bearer {token_madre}"}

    assert client.get(f"/api/v1/asignaciones/{asignacion_id}", headers=h_madre).status_code == 200
    assert client.get(f"/api/v1/asignaciones/{asignacion_id}/historial", headers=h_madre).status_code == 403
