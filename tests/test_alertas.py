"""Pruebas de Alertas y Evasiones (ADR-0009, sección 1): flujo de evasión, destinatarios,
respaldo obligatorio cuando no hay destinatarios resolubles, autorización y generación
automática de `visita_vencida` idempotente."""
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
    "nombres": "Valentina Prueba",
    "apellidos": "Sintética",
    "fecha_nacimiento": "2016-06-15",
}


def crear_menor(client, h):
    return client.post("/api/v1/menores", json=MENOR_SINTETICO, headers=h).json()["id"]


def ingresar_menor(client, h_admin, menor_id, hogar_id):
    return client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )


def _escenario_con_defensor_y_psicosocial(client, session_factory, sufijo, con_usuario=True, telefonos=None):
    """Monta menor + hogar + defensor/psicosocial asignados (con o sin cuenta de usuario)."""
    telefonos = telefonos or {}
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, f"admin_{sufijo}@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_defensor = crear_usuario(session_factory, f"defensor_{sufijo}@prueba.local", "defensor") if con_usuario else None
    defensor_id = crear_profesional(session_factory, uid_defensor, "defensor", telefono=telefonos.get("defensor"))
    asignar_profesional_a_menor(session_factory, menor_id, defensor_id, "defensor")

    uid_psico = crear_usuario(session_factory, f"psico_{sufijo}@prueba.local", "profesional") if con_usuario else None
    psico_id = crear_profesional(session_factory, uid_psico, "psicosocial", telefono=telefonos.get("psicosocial"))
    asignar_profesional_a_menor(session_factory, menor_id, psico_id, "psicosocial")

    return zona_id, hogar_id, h_admin, menor_id, uid_defensor, uid_psico


def test_flujo_evasion_destinatarios_y_contactos_emergencia(client, session_factory):
    zona_id, hogar_id, h_admin, menor_id, uid_defensor, uid_psico = _escenario_con_defensor_y_psicosocial(
        client, session_factory, "ev1", telefonos={"defensor": "300-111", "psicosocial": "300-222"}
    )

    r = client.post(
        "/api/v1/alertas/evasion", json={"menor_id": menor_id, "descripcion": "No llegó al colegio"}, headers=h_admin
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["alerta"]["tipo"] == "evasion"
    assert cuerpo["alerta"]["estado"] == "activa"
    destinatarios = {d["usuario_id"] for d in cuerpo["alerta"]["destinatarios"]}
    assert destinatarios == {uid_defensor, uid_psico}

    contactos = cuerpo["contactos_emergencia"]
    assert contactos["policia_infancia_telefono"]
    telefonos_por_rol = {c["rol_asignado"]: c["telefono"] for c in contactos["contactos"]}
    assert telefonos_por_rol == {"defensor": "300-111", "psicosocial": "300-222"}
    assert all(c["nota"] is None for c in contactos["contactos"])


def test_evasion_sin_telefono_registrado_lo_dice_explicitamente(client, session_factory):
    _, _, h_admin, menor_id, _, _ = _escenario_con_defensor_y_psicosocial(client, session_factory, "ev2")

    r = client.post(
        "/api/v1/alertas/evasion", json={"menor_id": menor_id, "descripcion": "Evasión"}, headers=h_admin
    )
    contactos = r.json()["contactos_emergencia"]["contactos"]
    for contacto in contactos:
        assert contacto["telefono"] is None
        assert contacto["nota"] == "Teléfono no registrado para este profesional"


def test_destinatario_marca_vista_y_aparece_en_mis_pendientes(client, session_factory):
    _, _, h_admin, menor_id, uid_defensor, uid_psico = _escenario_con_defensor_y_psicosocial(
        client, session_factory, "ev3"
    )
    r = client.post(
        "/api/v1/alertas/evasion", json={"menor_id": menor_id, "descripcion": "Evasión"}, headers=h_admin
    )
    alerta_id = r.json()["alerta"]["id"]

    h_defensor = {"Authorization": f"Bearer {login(client, 'defensor_ev3@prueba.local')}"}
    r = client.get("/api/v1/alertas/mis-pendientes", headers=h_defensor)
    assert any(a["id"] == alerta_id for a in r.json())

    r = client.put(f"/api/v1/alertas/{alerta_id}/visto", headers=h_defensor)
    assert r.status_code == 200

    r = client.get("/api/v1/alertas/mis-pendientes", headers=h_defensor)
    assert all(a["id"] != alerta_id for a in r.json())

    # el psicosocial, que no la ha visto, sigue viéndola en sus pendientes
    h_psico = {"Authorization": f"Bearer {login(client, 'psico_ev3@prueba.local')}"}
    r = client.get("/api/v1/alertas/mis-pendientes", headers=h_psico)
    assert any(a["id"] == alerta_id for a in r.json())


def test_no_destinatario_no_puede_marcar_vista(client, session_factory):
    _, _, h_admin, menor_id, _, _ = _escenario_con_defensor_y_psicosocial(client, session_factory, "ev4")
    r = client.post(
        "/api/v1/alertas/evasion", json={"menor_id": menor_id, "descripcion": "Evasión"}, headers=h_admin
    )
    alerta_id = r.json()["alerta"]["id"]

    uid_ajeno = crear_usuario(session_factory, "ajeno_ev4@prueba.local", "defensor")
    h_ajeno = {"Authorization": f"Bearer {login(client, 'ajeno_ev4@prueba.local')}"}

    r = client.put(f"/api/v1/alertas/{alerta_id}/visto", headers=h_ajeno)
    assert r.status_code == 403


def test_usuario_sin_relacion_con_el_menor_no_puede_ver_la_alerta(client, session_factory):
    _, _, h_admin, menor_id, _, _ = _escenario_con_defensor_y_psicosocial(client, session_factory, "ev5")
    r = client.post(
        "/api/v1/alertas/evasion", json={"menor_id": menor_id, "descripcion": "Evasión"}, headers=h_admin
    )
    alerta_id = r.json()["alerta"]["id"]

    # Defensor sin ninguna asignación: no es destinatario, no generó la alerta, no es
    # coordinador/admin/auditor -> denegado (ADR-0009, sección 1 "Autorización").
    uid_otro = crear_usuario(session_factory, "otro_defensor_ev5@prueba.local", "defensor")
    crear_profesional(session_factory, uid_otro, "defensor", nombres="Otro defensor")
    h_otro = {"Authorization": f"Bearer {login(client, 'otro_defensor_ev5@prueba.local')}"}

    r = client.get(f"/api/v1/alertas/{alerta_id}", headers=h_otro)
    assert r.status_code == 403


def test_madre_sin_asignacion_vigente_no_puede_reportar_evasion(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_ev6@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    # El menor nunca se asigna a ningún hogar: la madre de otro hogar no tiene relación con él.
    uid_madre = crear_usuario(session_factory, "madre_ev6@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-ev6")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_ev6@prueba.local')}"}

    r = client.post(
        "/api/v1/alertas/evasion", json={"menor_id": menor_id, "descripcion": "Evasión"}, headers=h_madre
    )
    assert r.status_code == 403


def test_auditor_no_puede_reportar_evasion(client, session_factory):
    _, _, h_admin, menor_id, _, _ = _escenario_con_defensor_y_psicosocial(client, session_factory, "ev7")
    h_auditor = auth_header(client, session_factory, "auditor_ev7@prueba.local", "auditor")
    r = client.post(
        "/api/v1/alertas/evasion", json={"menor_id": menor_id, "descripcion": "Evasión"}, headers=h_auditor
    )
    assert r.status_code == 403


def test_respaldo_coordinador_cuando_defensor_y_psicosocial_sin_usuario(client, session_factory):
    """Corrección obligatoria de seguridad (ADR-0009): si el defensor/psicosocial asignados no
    tienen cuenta de usuario, la alerta de evasión nunca queda con cero destinatarios."""
    zona_id, hogar_id, h_admin, menor_id, uid_defensor, uid_psico = _escenario_con_defensor_y_psicosocial(
        client, session_factory, "ev8", con_usuario=False
    )
    assert uid_defensor is None and uid_psico is None

    uid_coordinador = crear_usuario(session_factory, "coord_ev8@prueba.local", "coordinador", zona_id=zona_id)

    r = client.post(
        "/api/v1/alertas/evasion", json={"menor_id": menor_id, "descripcion": "Evasión"}, headers=h_admin
    )
    assert r.status_code == 200
    destinatarios = {d["usuario_id"] for d in r.json()["alerta"]["destinatarios"]}
    assert len(destinatarios) >= 1
    assert destinatarios == {uid_coordinador}


def test_respaldo_admin_cuando_no_hay_coordinador_de_zona(client, session_factory):
    """Sin coordinador resoluble en la zona, el respaldo cae a cualquier admin; nunca cero
    destinatarios."""
    zona_id, hogar_id, h_admin, menor_id, uid_defensor, uid_psico = _escenario_con_defensor_y_psicosocial(
        client, session_factory, "ev9", con_usuario=False
    )
    assert uid_defensor is None and uid_psico is None

    r = client.post(
        "/api/v1/alertas/evasion", json={"menor_id": menor_id, "descripcion": "Evasión"}, headers=h_admin
    )
    assert r.status_code == 200
    destinatarios = {d["usuario_id"] for d in r.json()["alerta"]["destinatarios"]}
    assert len(destinatarios) >= 1


def test_generacion_automatica_visita_vencida_sin_duplicados(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_va1@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    client.post(
        "/api/v1/citas",
        json={"menor_id": menor_id, "tipo": "medica", "fecha_hora": "2020-01-01T10:00:00Z"},
        headers=h_admin,
    )

    r1 = client.post("/api/v1/alertas/generar-automaticas", headers=h_admin)
    assert r1.status_code == 200
    # Desde ADR-0010 (sección 1.7), `generar-automaticas` también evalúa "sin informe
    # psicosocial en 60 días": un menor recién ingresado sin reportes también dispara
    # `documento_faltante` en la misma pasada, además de `visita_vencida`.
    visitas_r1 = [a for a in r1.json() if a["tipo"] == "visita_vencida"]
    assert len(visitas_r1) == 1

    r2 = client.post("/api/v1/alertas/generar-automaticas", headers=h_admin)
    assert r2.status_code == 200
    assert len(r2.json()) == 0  # idempotente: nada nuevo que generar en la segunda pasada

    r3 = client.get("/api/v1/alertas", params={"menor_id": menor_id, "tipo": "visita_vencida"}, headers=h_admin)
    assert len(r3.json()) == 1


def test_generar_automaticas_denegado_a_profesional(client, session_factory):
    _, _, h_admin, menor_id, uid_defensor, _ = _escenario_con_defensor_y_psicosocial(client, session_factory, "va2")
    h_defensor = {"Authorization": f"Bearer {login(client, 'defensor_va2@prueba.local')}"}
    r = client.post("/api/v1/alertas/generar-automaticas", headers=h_defensor)
    assert r.status_code == 403


def test_auditor_ve_alerta_pero_sin_descripcion_ni_detalle(client, session_factory):
    """Corrección de seguridad (ADR-0009, sección 1): el auditor solo ve metadatos (tipo, menor,
    fecha, estado, destinatarios y si cada uno la vio), nunca `descripcion`/`detalle`."""
    _, _, h_admin, menor_id, uid_defensor, uid_psico = _escenario_con_defensor_y_psicosocial(
        client, session_factory, "ev10"
    )
    r = client.post(
        "/api/v1/alertas/evasion",
        json={"menor_id": menor_id, "descripcion": "Circunstancia sensible del caso"},
        headers=h_admin,
    )
    alerta_id = r.json()["alerta"]["id"]

    h_auditor = auth_header(client, session_factory, "auditor_ev10@prueba.local", "auditor")

    r = client.get(f"/api/v1/alertas/{alerta_id}", headers=h_auditor)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["tipo"] == "evasion"
    assert cuerpo["estado"] == "activa"
    assert {d["usuario_id"] for d in cuerpo["destinatarios"]} == {uid_defensor, uid_psico}
    assert cuerpo["descripcion"] != "Circunstancia sensible del caso"
    assert cuerpo["detalle"] is None

    r = client.get("/api/v1/alertas", params={"menor_id": menor_id}, headers=h_auditor)
    assert r.status_code == 200
    assert all(a["descripcion"] != "Circunstancia sensible del caso" for a in r.json())

    # Quien sí tiene relación con el caso (admin que la generó) sigue viendo el texto completo.
    r = client.get(f"/api/v1/alertas/{alerta_id}", headers=h_admin)
    assert r.json()["descripcion"] == "Circunstancia sensible del caso"


def test_panel_dispara_generacion_automatica(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_coord = auth_header(client, session_factory, "coord_panel1@prueba.local", "coordinador", zona_id=zona_id)
    menor_id = crear_menor(client, h_coord)
    ingresar_menor(client, h_coord, menor_id, hogar_id)

    client.post(
        "/api/v1/citas",
        json={"menor_id": menor_id, "tipo": "medica", "fecha_hora": "2020-01-01T10:00:00Z"},
        headers=h_coord,
    )

    r = client.get("/api/v1/alertas/panel", headers=h_coord)
    assert r.status_code == 200
    assert any(a["tipo"] == "visita_vencida" and a["menor_id"] == menor_id for a in r.json())
