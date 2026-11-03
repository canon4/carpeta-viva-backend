"""Pruebas de Gestión Documental (ADR-0008): creación, flujo de aprobación, versionado,
autorización por sección y exclusión del auditor del contenido descifrado.
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
    "nombres": "Sofía Prueba",
    "apellidos": "Sintética",
    "fecha_nacimiento": "2017-02-20",
}


def crear_menor(client, h):
    return client.post("/api/v1/menores", json=MENOR_SINTETICO, headers=h).json()["id"]


def ingresar_menor(client, h_admin, menor_id, hogar_id):
    return client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )


def archivo(nombre="prueba.txt", contenido=b"contenido sintetico de prueba", tipo="text/plain"):
    return {"archivo": (nombre, contenido, tipo)}


def test_madre_sin_permiso_seccion_no_crea_documento_salud(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_doc1@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_madre = crear_usuario(session_factory, "madre_doc1@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-1")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_doc1@prueba.local')}"}

    r = client.post(
        "/api/v1/documentos",
        data={"menor_id": menor_id, "categoria": "salud", "titulo": "Historia clínica"},
        files=archivo(),
        headers=h_madre,
    )
    assert r.status_code == 403


def test_madre_con_permiso_seccion_crea_documento_salud_en_borrador(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_doc2@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_madre = crear_usuario(session_factory, "madre_doc2@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-2")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)

    uid_defensor = crear_usuario(session_factory, "defensor_doc2@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_defensor, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    h_defensor = {"Authorization": f"Bearer {login(client, 'defensor_doc2@prueba.local')}"}
    client.post(
        f"/api/v1/menores/{menor_id}/permisos",
        json={"seccion": "salud", "usuario_id": uid_madre},
        headers=h_defensor,
    )

    h_madre = {"Authorization": f"Bearer {login(client, 'madre_doc2@prueba.local')}"}
    r = client.post(
        "/api/v1/documentos",
        data={"menor_id": menor_id, "categoria": "salud", "titulo": "Historia clínica"},
        files=archivo(),
        headers=h_madre,
    )
    assert r.status_code == 201
    assert r.json()["estado_flujo"] == "borrador"
    assert r.json()["version"] == 1
    assert r.json()["sensible"] is True


def test_profesional_asignado_crea_documento_directo_en_aprobado(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_doc3@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_psico = crear_usuario(session_factory, "psico_doc3@prueba.local", "profesional")
    profesional_id = crear_profesional(session_factory, uid_psico, "psicosocial")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "psicosocial")
    h_psico = {"Authorization": f"Bearer {login(client, 'psico_doc3@prueba.local')}"}

    r = client.post(
        "/api/v1/documentos",
        data={"menor_id": menor_id, "categoria": "psicosocial", "titulo": "Informe inicial"},
        files=archivo(),
        headers=h_psico,
    )
    assert r.status_code == 201
    assert r.json()["estado_flujo"] == "aprobado"


def _crear_menor_con_defensor_y_permiso_salud(client, session_factory, sufijo):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, f"admin_{sufijo}@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_madre = crear_usuario(session_factory, f"madre_{sufijo}@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, f"900-{sufijo}")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)

    uid_defensor = crear_usuario(session_factory, f"defensor_{sufijo}@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_defensor, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    h_defensor = {"Authorization": f"Bearer {login(client, f'defensor_{sufijo}@prueba.local')}"}
    client.post(
        f"/api/v1/menores/{menor_id}/permisos",
        json={"seccion": "salud", "usuario_id": uid_madre},
        headers=h_defensor,
    )
    h_madre = {"Authorization": f"Bearer {login(client, f'madre_{sufijo}@prueba.local')}"}
    return h_admin, h_defensor, h_madre, menor_id, uid_madre


def test_flujo_enviar_y_aprobar(client, session_factory):
    h_admin, h_defensor, h_madre, menor_id, _ = _crear_menor_con_defensor_y_permiso_salud(
        client, session_factory, "flujo1"
    )
    r = client.post(
        "/api/v1/documentos",
        data={"menor_id": menor_id, "categoria": "salud", "titulo": "Historia clínica"},
        files=archivo(),
        headers=h_madre,
    )
    documento_id = r.json()["id"]

    r = client.put(f"/api/v1/documentos/{documento_id}/enviar", headers=h_madre)
    assert r.status_code == 200
    assert r.json()["estado_flujo"] == "en_revision"

    r = client.put(f"/api/v1/documentos/{documento_id}/aprobar", headers=h_defensor)
    assert r.status_code == 200
    assert r.json()["estado_flujo"] == "aprobado"
    assert r.json()["revisado_por"] is not None


def test_flujo_enviar_y_devolver(client, session_factory):
    h_admin, h_defensor, h_madre, menor_id, _ = _crear_menor_con_defensor_y_permiso_salud(
        client, session_factory, "flujo2"
    )
    r = client.post(
        "/api/v1/documentos",
        data={"menor_id": menor_id, "categoria": "salud", "titulo": "Historia clínica"},
        files=archivo(),
        headers=h_madre,
    )
    documento_id = r.json()["id"]
    client.put(f"/api/v1/documentos/{documento_id}/enviar", headers=h_madre)

    r = client.put(
        f"/api/v1/documentos/{documento_id}/devolver", json={"motivo": "falta firma"}, headers=h_defensor
    )
    assert r.status_code == 200
    assert r.json()["estado_flujo"] == "devuelto"
    assert r.json()["motivo_devolucion"] == "falta firma"


def test_versionado_snapshotea_y_sube_version(client, session_factory):
    h_admin, h_defensor, h_madre, menor_id, _ = _crear_menor_con_defensor_y_permiso_salud(
        client, session_factory, "ver1"
    )
    r = client.post(
        "/api/v1/documentos",
        data={"menor_id": menor_id, "categoria": "salud", "titulo": "Historia clínica"},
        files=archivo(contenido=b"version 1"),
        headers=h_madre,
    )
    documento_id = r.json()["id"]
    client.put(f"/api/v1/documentos/{documento_id}/enviar", headers=h_madre)
    client.put(f"/api/v1/documentos/{documento_id}/devolver", json={"motivo": "corregir"}, headers=h_defensor)

    r = client.post(
        f"/api/v1/documentos/{documento_id}/version", files=archivo(contenido=b"version 2 corregida"), headers=h_madre
    )
    assert r.status_code == 200
    assert r.json()["version"] == 2
    assert r.json()["estado_flujo"] == "en_revision"

    r = client.get(f"/api/v1/documentos/{documento_id}/versiones", headers=h_madre)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["version"] == 1
    assert r.json()[0]["estado_flujo"] == "devuelto"

    r = client.get(f"/api/v1/documentos/{documento_id}/contenido", headers=h_madre)
    assert r.content == b"version 2 corregida"

    r = client.get(f"/api/v1/documentos/{documento_id}/versiones/1/contenido", headers=h_madre)
    assert r.content == b"version 1"


def test_auditor_sin_acceso_a_contenido_pero_si_a_metadatos(client, session_factory):
    """Categoría no sensible (`identidad`, sección None): el auditor sí ve metadatos vía
    `puede_ver_menor` (regla 2 de ADR-0008 sección 4), pero nunca el contenido descifrado
    (corrección obligatoria de seguridad), ni el de versiones anteriores."""
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_aud1@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_defensor = crear_usuario(session_factory, "defensor_aud1@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_defensor, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    h_defensor = {"Authorization": f"Bearer {login(client, 'defensor_aud1@prueba.local')}"}

    uid_madre = crear_usuario(session_factory, "madre_aud1@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-aud1")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_aud1@prueba.local')}"}

    r = client.post(
        "/api/v1/documentos",
        data={"menor_id": menor_id, "categoria": "identidad", "titulo": "Registro civil"},
        files=archivo(contenido=b"version 1"),
        headers=h_madre,
    )
    documento_id = r.json()["id"]
    assert r.json()["estado_flujo"] == "borrador"
    assert r.json()["sensible"] is False

    client.put(f"/api/v1/documentos/{documento_id}/enviar", headers=h_madre)
    client.put(f"/api/v1/documentos/{documento_id}/devolver", json={"motivo": "corregir"}, headers=h_defensor)
    # Nueva versión: deja un snapshot (version 1) que el auditor tampoco debe poder descargar.
    client.post(f"/api/v1/documentos/{documento_id}/version", files=archivo(contenido=b"version 2"), headers=h_madre)

    h_auditor = auth_header(client, session_factory, "auditor_doc1@prueba.local", "auditor")

    r = client.get(f"/api/v1/documentos/{documento_id}", headers=h_auditor)
    assert r.status_code == 200

    r = client.get(f"/api/v1/documentos/{documento_id}/contenido", headers=h_auditor)
    assert r.status_code == 403

    r = client.get(f"/api/v1/documentos/{documento_id}/versiones/1/contenido", headers=h_auditor)
    assert r.status_code == 403


def test_descarga_denegada_sin_permiso_seccion(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_doc4@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_psico = crear_usuario(session_factory, "psico_doc4@prueba.local", "profesional")
    profesional_id = crear_profesional(session_factory, uid_psico, "psicosocial")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "psicosocial")
    h_psico = {"Authorization": f"Bearer {login(client, 'psico_doc4@prueba.local')}"}

    r = client.post(
        "/api/v1/documentos",
        data={"menor_id": menor_id, "categoria": "psicosocial", "titulo": "Informe"},
        files=archivo(),
        headers=h_psico,
    )
    documento_id = r.json()["id"]

    uid_madre = crear_usuario(session_factory, "madre_doc4@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-4")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_doc4@prueba.local')}"}

    r = client.get(f"/api/v1/documentos/{documento_id}/contenido", headers=h_madre)
    assert r.status_code == 403


def test_endpoint_agregador_por_seccion(client, session_factory):
    h_admin, h_defensor, h_madre, menor_id, uid_madre = _crear_menor_con_defensor_y_permiso_salud(
        client, session_factory, "sec1"
    )
    client.post(
        "/api/v1/documentos",
        data={"menor_id": menor_id, "categoria": "salud", "titulo": "Historia clínica"},
        files=archivo(),
        headers=h_madre,
    )
    client.post(
        "/api/v1/documentos/reportes",
        json={"menor_id": menor_id, "tipo_reporte": "informe_medico", "contenido": {"nota": "control de rutina"}},
        headers=h_defensor,
    )

    r = client.get(f"/api/v1/documentos/menor/{menor_id}/seccion/salud", headers=h_madre)
    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo["documentos"]) == 1
    assert len(cuerpo["reportes"]) == 1

    uid_otra = crear_usuario(session_factory, "madre_sec_ajena@prueba.local", "madre")
    h_otra_madre = {"Authorization": f"Bearer {login(client, 'madre_sec_ajena@prueba.local')}"}
    r = client.get(f"/api/v1/documentos/menor/{menor_id}/seccion/salud", headers=h_otra_madre)
    assert r.status_code == 403
