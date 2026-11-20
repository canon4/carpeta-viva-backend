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
    "nombres": "Luna Prueba",
    "apellidos": "Sintética",
    "fecha_nacimiento": "2015-05-01",
    "genero": "femenino",
}


def crear_menor(client, h, **extra):
    datos = {**MENOR_SINTETICO, **extra}
    return client.post("/api/v1/menores", json=datos, headers=h)


def test_admin_crea_y_lista_menor(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    r = crear_menor(client, h)
    assert r.status_code == 201
    assert r.json()["estado_actual"] == "activo"
    assert r.json()["version"] == 1

    r = client.get("/api/v1/menores", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_crear_menor_sin_token_es_401(client):
    assert crear_menor(client, {}).status_code == 401


def test_profesional_generico_no_defensor_no_crea_menor(client, session_factory):
    uid = crear_usuario(session_factory, "psico1@prueba.local", "profesional")
    crear_profesional(session_factory, uid, "psicosocial")
    token = login(client, "psico1@prueba.local")
    h = {"Authorization": f"Bearer {token}"}
    assert crear_menor(client, h).status_code == 403


def test_actualizar_menor_genera_historial(client, session_factory):
    h = auth_header(client, session_factory, "admin2@prueba.local", "admin")
    menor_id = crear_menor(client, h).json()["id"]

    r = client.put(
        f"/api/v1/menores/{menor_id}",
        json={"nombres": "Luna Actualizada", "motivo": "corrección de datos"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["nombres"] == "Luna Actualizada"
    assert r.json()["version"] == 2

    r = client.get(f"/api/v1/menores/{menor_id}/historial", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["nombres"] == "Luna Prueba"
    assert r.json()[0]["version"] == 1


def test_profesional_no_asignado_no_puede_ver_menor(client, session_factory):
    h_admin = auth_header(client, session_factory, "admin3@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin).json()["id"]

    uid = crear_usuario(session_factory, "psico2@prueba.local", "profesional")
    crear_profesional(session_factory, uid, "psicosocial")
    token = login(client, "psico2@prueba.local")
    h = {"Authorization": f"Bearer {token}"}

    assert client.get(f"/api/v1/menores/{menor_id}", headers=h).status_code == 403


def test_profesional_asignado_ve_menor_pero_coordinador_no_ve_familia(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin4@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin).json()["id"]
    client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )

    uid_prof = crear_usuario(session_factory, "defensor1@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_prof, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    token_prof = login(client, "defensor1@prueba.local")
    h_prof = {"Authorization": f"Bearer {token_prof}"}

    r = client.get(f"/api/v1/menores/{menor_id}", headers=h_prof)
    assert r.status_code == 200

    r = client.get(f"/api/v1/menores/{menor_id}/familiares", headers=h_prof)
    assert r.status_code == 200  # el profesional asignado sí ve la sección sensible

    h_coord = auth_header(client, session_factory, "coord1@prueba.local", "coordinador", zona_id=zona_id)
    r = client.get(f"/api/v1/menores/{menor_id}", headers=h_coord)
    assert r.status_code == 200  # datos básicos sí

    r = client.get(f"/api/v1/menores/{menor_id}/familiares", headers=h_coord)
    assert r.status_code == 403  # sección sensible, no por defecto (ADR-0007 punto 2)

    h_auditor = auth_header(client, session_factory, "auditor1@prueba.local", "auditor")
    r = client.get(f"/api/v1/menores/{menor_id}/familiares", headers=h_auditor)
    assert r.status_code == 403  # auditor: solo metadatos (ADR-0007 punto 3)


def test_coordinador_de_otra_zona_no_ve_el_menor(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, "Zona A")
    otra_zona_id, _ = crear_zona_y_hogar(session_factory, "Zona B")

    h_admin = auth_header(client, session_factory, "admin5@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin).json()["id"]
    client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )

    h_coord_otra = auth_header(client, session_factory, "coord2@prueba.local", "coordinador", zona_id=otra_zona_id)
    assert client.get(f"/api/v1/menores/{menor_id}", headers=h_coord_otra).status_code == 403


def test_madre_necesita_asignacion_vigente_y_permiso_de_seccion(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin6@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin).json()["id"]

    uid_madre = crear_usuario(session_factory, "madre1@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-1")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    token_madre = login(client, "madre1@prueba.local")
    h_madre = {"Authorization": f"Bearer {token_madre}"}

    # Sin asignación todavía: no ve el menor.
    assert client.get(f"/api/v1/menores/{menor_id}", headers=h_madre).status_code == 403

    client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )

    # Con asignación vigente: ve datos básicos.
    assert client.get(f"/api/v1/menores/{menor_id}", headers=h_madre).status_code == 200

    # Pero no la familia sin permiso explícito del defensor.
    assert client.get(f"/api/v1/menores/{menor_id}/familiares", headers=h_madre).status_code == 403

    uid_defensor = crear_usuario(session_factory, "defensor2@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_defensor, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    token_defensor = login(client, "defensor2@prueba.local")
    h_defensor = {"Authorization": f"Bearer {token_defensor}"}

    r = client.post(
        f"/api/v1/menores/{menor_id}/permisos",
        json={"seccion": "familia", "usuario_id": str(uid_madre)},
        headers=h_defensor,
    )
    assert r.status_code == 201
    permiso_id = r.json()["id"]

    assert client.get(f"/api/v1/menores/{menor_id}/familiares", headers=h_madre).status_code == 200

    r = client.delete(f"/api/v1/menores/{menor_id}/permisos/{permiso_id}", headers=h_defensor)
    assert r.status_code == 200
    assert r.json()["activo"] is False

    assert client.get(f"/api/v1/menores/{menor_id}/familiares", headers=h_madre).status_code == 403


def test_madre_conserva_acceso_a_otro_menor_tras_cerrar_asignacion_de_uno(client, session_factory):
    """La madre atiende a más de un NNA en su hogar. Cerrar la asignación de uno (RF7) no debe
    afectar su acceso al expediente del otro, que sigue con asignación vigente."""
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin8@prueba.local", "admin")
    menor_a_id = crear_menor(client, h_admin).json()["id"]
    menor_b_id = crear_menor(client, h_admin, numero_documento="DOC-B-001").json()["id"]

    uid_madre = crear_usuario(session_factory, "madre3@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-2")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)

    r_a = client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_a_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )
    asignacion_a_id = r_a.json()["id"]
    client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_b_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )

    token_madre = login(client, "madre3@prueba.local")
    h_madre = {"Authorization": f"Bearer {token_madre}"}
    assert client.get(f"/api/v1/menores/{menor_a_id}", headers=h_madre).status_code == 200
    assert client.get(f"/api/v1/menores/{menor_b_id}", headers=h_madre).status_code == 200

    r = client.put(
        f"/api/v1/asignaciones/{asignacion_a_id}/cerrar",
        json={"motivo": "egreso del menor A"},
        headers=h_admin,
    )
    assert r.status_code == 200

    # El menor A sale: la madre pierde acceso a su expediente (RF7)...
    assert client.get(f"/api/v1/menores/{menor_a_id}", headers=h_madre).status_code == 403
    # ...pero conserva el acceso al menor B, cuya asignación sigue vigente en el mismo hogar.
    assert client.get(f"/api/v1/menores/{menor_b_id}", headers=h_madre).status_code == 200


def test_profesional_no_defensor_no_otorga_ni_revoca_permiso(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin7@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin).json()["id"]

    uid_madre = crear_usuario(session_factory, "madre2@prueba.local", "madre")

    uid_psico = crear_usuario(session_factory, "psico3@prueba.local", "profesional")
    profesional_id = crear_profesional(session_factory, uid_psico, "psicosocial")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "psicosocial")
    token_psico = login(client, "psico3@prueba.local")
    h_psico = {"Authorization": f"Bearer {token_psico}"}

    r = client.post(
        f"/api/v1/menores/{menor_id}/permisos",
        json={"seccion": "familia", "usuario_id": str(uid_madre)},
        headers=h_psico,
    )
    assert r.status_code == 403


def _escenario_defensor_y_madre(client, session_factory, sufijo):
    """Menor asignado a un hogar con madre con cuenta y un defensor asignado."""
    _, hogar_id = crear_zona_y_hogar(session_factory, f"Zona permisos {sufijo}")
    h_admin = auth_header(client, session_factory, f"admin-perm-{sufijo}@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin).json()["id"]
    uid_madre = crear_usuario(session_factory, f"madre-perm-{sufijo}@prueba.local", "madre")
    vincular_hogar_madre(session_factory, hogar_id, crear_madre(session_factory, uid_madre, f"950-{sufijo}"))
    client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )
    uid_defensor = crear_usuario(session_factory, f"defensor-perm-{sufijo}@prueba.local", "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, crear_profesional(session_factory, uid_defensor, "defensor"), "defensor")
    h_defensor = {"Authorization": f"Bearer {login(client, f'defensor-perm-{sufijo}@prueba.local')}"}
    return menor_id, uid_madre, h_defensor


def test_permiso_sin_usuario_se_otorga_a_la_madre_del_hogar_vigente(client, session_factory):
    menor_id, uid_madre, h_defensor = _escenario_defensor_y_madre(client, session_factory, "a")
    r = client.post(f"/api/v1/menores/{menor_id}/permisos", json={"seccion": "salud"}, headers=h_defensor)
    assert r.status_code == 201
    assert r.json()["usuario_id"] == uid_madre


def test_no_se_otorga_permiso_a_una_madre_de_otro_hogar(client, session_factory):
    menor_id, _, h_defensor = _escenario_defensor_y_madre(client, session_factory, "b")
    uid_otra = crear_usuario(session_factory, "madre-otra-b@prueba.local", "madre")
    _, hogar_otro = crear_zona_y_hogar(session_factory, "Zona otra b")
    vincular_hogar_madre(session_factory, hogar_otro, crear_madre(session_factory, uid_otra, "951-b"))
    r = client.post(
        f"/api/v1/menores/{menor_id}/permisos", json={"seccion": "salud", "usuario_id": uid_otra}, headers=h_defensor
    )
    assert r.status_code == 422


def test_hogar_vigente_muestra_nombres_y_excluye_al_auditor(client, session_factory):
    menor_id, uid_madre, h_defensor = _escenario_defensor_y_madre(client, session_factory, "c")
    r = client.get(f"/api/v1/menores/{menor_id}/hogar-vigente", headers=h_defensor)
    assert r.status_code == 200
    assert r.json()["madre_nombre"]
    assert r.json()["madre_usuario_id"] == uid_madre
    assert r.json()["zona_nombre"] == "Zona permisos c"
    h_auditor = auth_header(client, session_factory, "auditor-perm-c@prueba.local", "auditor")
    assert client.get(f"/api/v1/menores/{menor_id}/hogar-vigente", headers=h_auditor).status_code == 403
