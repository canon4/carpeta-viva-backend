"""Pruebas de Citas y Recordatorios (ADR-0009, sección 2): autorización por fila y el filtrado
de `notas` por sección (corrección obligatoria de seguridad)."""
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
    "nombres": "Camila Prueba",
    "apellidos": "Sintética",
    "fecha_nacimiento": "2017-09-01",
}


def crear_menor(client, h):
    return client.post("/api/v1/menores", json=MENOR_SINTETICO, headers=h).json()["id"]


def ingresar_menor(client, h_admin, menor_id, hogar_id):
    return client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )


def test_crear_y_obtener_cita(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_c1@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    r = client.post(
        "/api/v1/citas",
        json={
            "menor_id": menor_id,
            "tipo": "otro",
            "fecha_hora": "2026-06-01T09:00:00Z",
            "lugar": "Consultorio 3",
            "notas": "Traer carné de vacunas",
        },
        headers=h_admin,
    )
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["estado"] == "pendiente"
    assert cuerpo["lugar"] == "Consultorio 3"
    assert cuerpo["notas"] == "Traer carné de vacunas"

    r = client.get(f"/api/v1/citas/{cuerpo['id']}", headers=h_admin)
    assert r.status_code == 200
    assert r.json()["notas"] == "Traer carné de vacunas"


def test_notas_ocultas_sin_permiso_de_seccion_pero_resto_de_fila_visible(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_c2@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_madre = crear_usuario(session_factory, "madre_c2@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-c2")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_c2@prueba.local')}"}

    r = client.post(
        "/api/v1/citas",
        json={
            "menor_id": menor_id,
            "tipo": "psicosocial",
            "fecha_hora": "2026-06-01T09:00:00Z",
            "lugar": "Consultorio 5",
            "notas": "Sospecha de maltrato, citar a valoración",
        },
        headers=h_admin,
    )
    cita_id = r.json()["id"]

    # La madre puede ver al menor (asignación vigente) pero no tiene permiso de sección
    # "psicosocial": ve el resto de la fila, nunca las notas.
    r = client.get(f"/api/v1/citas/{cita_id}", headers=h_madre)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["tipo"] == "psicosocial"
    assert cuerpo["lugar"] == "Consultorio 5"
    assert cuerpo["estado"] == "pendiente"
    assert cuerpo["notas"] is None

    # El defensor asignado al menor otorga permiso de sección "psicosocial" a la madre.
    uid_defensor = crear_usuario(session_factory, "defensor_c2@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_defensor, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    h_defensor = {"Authorization": f"Bearer {login(client, 'defensor_c2@prueba.local')}"}
    client.post(
        f"/api/v1/menores/{menor_id}/permisos",
        json={"seccion": "psicosocial", "usuario_id": uid_madre},
        headers=h_defensor,
    )

    r = client.get(f"/api/v1/citas/{cita_id}", headers=h_madre)
    assert r.json()["notas"] == "Sospecha de maltrato, citar a valoración"


def test_notas_de_tipo_otro_visibles_sin_permiso_de_seccion(client, session_factory):
    """`otro` no tiene sección sensible asociada (ADR-0009): visible con solo `puede_ver_menor`."""
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_c3@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_madre = crear_usuario(session_factory, "madre_c3@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-c3")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_c3@prueba.local')}"}

    r = client.post(
        "/api/v1/citas",
        json={"menor_id": menor_id, "tipo": "otro", "fecha_hora": "2026-06-01T09:00:00Z", "notas": "Recordatorio simple"},
        headers=h_admin,
    )
    cita_id = r.json()["id"]

    r = client.get(f"/api/v1/citas/{cita_id}", headers=h_madre)
    assert r.json()["notas"] == "Recordatorio simple"


def test_usuario_sin_relacion_con_el_menor_no_ve_la_cita(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_c4@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    r = client.post(
        "/api/v1/citas",
        json={"menor_id": menor_id, "tipo": "medica", "fecha_hora": "2026-06-01T09:00:00Z"},
        headers=h_admin,
    )
    cita_id = r.json()["id"]

    h_ajeno = auth_header(client, session_factory, "defensor_c4@prueba.local", "defensor")
    r = client.get(f"/api/v1/citas/{cita_id}", headers=h_ajeno)
    assert r.status_code == 403

    r = client.get("/api/v1/citas", params={"menor_id": menor_id}, headers=h_ajeno)
    assert r.status_code == 200
    assert r.json() == []


def test_auditor_no_puede_crear_cita(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_c5@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    h_auditor = auth_header(client, session_factory, "auditor_c5@prueba.local", "auditor")
    r = client.post(
        "/api/v1/citas",
        json={"menor_id": menor_id, "tipo": "medica", "fecha_hora": "2026-06-01T09:00:00Z"},
        headers=h_auditor,
    )
    assert r.status_code == 403


def test_proximas_solo_pendientes_futuras_y_cambio_de_estado(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_c6@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    r_futura = client.post(
        "/api/v1/citas",
        json={"menor_id": menor_id, "tipo": "medica", "fecha_hora": "2099-01-01T09:00:00Z"},
        headers=h_admin,
    )
    r_pasada = client.post(
        "/api/v1/citas",
        json={"menor_id": menor_id, "tipo": "medica", "fecha_hora": "2020-01-01T09:00:00Z"},
        headers=h_admin,
    )
    cita_futura_id = r_futura.json()["id"]
    cita_pasada_id = r_pasada.json()["id"]

    r = client.get("/api/v1/citas/proximas", headers=h_admin)
    ids = {c["id"] for c in r.json()}
    assert cita_futura_id in ids
    assert cita_pasada_id not in ids

    r = client.put(f"/api/v1/citas/{cita_futura_id}/estado", json={"estado": "cumplida"}, headers=h_admin)
    assert r.status_code == 200
    assert r.json()["estado"] == "cumplida"

    r = client.get("/api/v1/citas/proximas", headers=h_admin)
    ids = {c["id"] for c in r.json()}
    assert cita_futura_id not in ids


def test_reprogramar_cita(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_c7@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    r = client.post(
        "/api/v1/citas",
        json={"menor_id": menor_id, "tipo": "medica", "fecha_hora": "2026-06-01T09:00:00Z", "lugar": "Consultorio 1"},
        headers=h_admin,
    )
    cita_id = r.json()["id"]

    r = client.put(
        f"/api/v1/citas/{cita_id}",
        json={"fecha_hora": "2026-07-01T10:00:00Z", "lugar": "Consultorio 2"},
        headers=h_admin,
    )
    assert r.status_code == 200
    assert r.json()["lugar"] == "Consultorio 2"
