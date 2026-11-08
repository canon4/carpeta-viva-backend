"""Pruebas de Archivo y Cierre (ADR-0010, sección 3): condición de disparo, alcance de zona
del coordinador en los cuatro endpoints, exclusión del auditor del paquete descifrado, y
bloqueo de escritura (documentos/alertas/citas) tras archivar."""
import io
import zipfile

from ._helpers import auth_header, crear_usuario, crear_zona_y_hogar, login

MENOR_SINTETICO = {
    "nombres": "Camila Prueba",
    "apellidos": "Sintética",
    "fecha_nacimiento": "2015-03-10",
}


def crear_menor(client, h):
    return client.post("/api/v1/menores", json=MENOR_SINTETICO, headers=h).json()["id"]


def ingresar_menor(client, h_admin, menor_id, hogar_id):
    r = client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )
    assert r.status_code == 201
    return r.json()["id"]


def cerrar_asignacion(client, h_admin, asignacion_id):
    r = client.put(
        f"/api/v1/asignaciones/{asignacion_id}/cerrar",
        json={"fecha_fin": "2026-06-01", "motivo": "egreso por reintegro familiar"},
        headers=h_admin,
    )
    assert r.status_code == 200
    return r


def _menor_egresado(client, h_admin, hogar_id):
    """Menor con `estado_actual=egresado` y sin asignación vigente: cumple la condición de
    archivo (ADR-0010, sección 3.1)."""
    menor_id = crear_menor(client, h_admin)
    asignacion_id = ingresar_menor(client, h_admin, menor_id, hogar_id)
    cerrar_asignacion(client, h_admin, asignacion_id)
    return menor_id


def test_condicion_no_cumplida_con_asignacion_vigente_es_409(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_arch1@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    r = client.post(
        f"/api/v1/archivo/menores/{menor_id}/cerrar", json={"motivo": "intento prematuro"}, headers=h_admin
    )
    assert r.status_code == 409


def test_admin_puede_cerrar_expediente_y_queda_archivado(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_arch2@prueba.local", "admin")
    menor_id = _menor_egresado(client, h_admin, hogar_id)

    r = client.post(
        f"/api/v1/archivo/menores/{menor_id}/cerrar", json={"motivo": "cierre de caso"}, headers=h_admin
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado"] == "archivado"
    assert cuerpo["paquete_hash"]
    assert cuerpo["zona_id"] == zona_id

    # Reintentar cerrar un expediente ya archivado es un conflicto, no un éxito silencioso.
    r2 = client.post(
        f"/api/v1/archivo/menores/{menor_id}/cerrar", json={"motivo": "doble cierre"}, headers=h_admin
    )
    assert r2.status_code == 409


def test_coordinador_fuera_de_zona_no_puede_cerrar_ni_consultar(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory, nombre_zona="Zona del expediente")
    otra_zona_id, _otro_hogar = crear_zona_y_hogar(session_factory, nombre_zona="Otra zona")
    h_admin = auth_header(client, session_factory, "admin_arch3@prueba.local", "admin")
    menor_id = _menor_egresado(client, h_admin, hogar_id)

    h_coord_ajeno = auth_header(
        client, session_factory, "coord_ajeno_arch3@prueba.local", "coordinador", zona_id=otra_zona_id
    )

    r = client.post(
        f"/api/v1/archivo/menores/{menor_id}/cerrar", json={"motivo": "cierre"}, headers=h_coord_ajeno
    )
    assert r.status_code == 403

    r = client.get(f"/api/v1/archivo/menores/{menor_id}", headers=h_coord_ajeno)
    assert r.status_code == 403

    r = client.get(f"/api/v1/archivo/menores/{menor_id}/paquete", headers=h_coord_ajeno)
    assert r.status_code == 403


def test_coordinador_de_la_zona_puede_cerrar_consultar_y_descargar(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_arch4@prueba.local", "admin")
    menor_id = _menor_egresado(client, h_admin, hogar_id)

    h_coord = auth_header(client, session_factory, "coord_arch4@prueba.local", "coordinador", zona_id=zona_id)

    r = client.post(f"/api/v1/archivo/menores/{menor_id}/cerrar", json={"motivo": "cierre de caso"}, headers=h_coord)
    assert r.status_code == 200

    r = client.get(f"/api/v1/archivo/menores/{menor_id}", headers=h_coord)
    assert r.status_code == 200
    assert r.json()["estado"] == "archivado"

    r = client.get(f"/api/v1/archivo/menores/{menor_id}/paquete", headers=h_coord)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert "manifest.json" in zf.namelist()


def test_estado_sin_archivar_responde_activo_sin_crear_fila_persistente(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_arch5@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)

    r = client.get(f"/api/v1/archivo/menores/{menor_id}", headers=h_admin)
    assert r.status_code == 200
    assert r.json()["estado"] == "activo"
    assert r.json()["archivado_en"] is None


def test_auditor_ve_estado_pero_nunca_descarga_el_paquete(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_arch6@prueba.local", "admin")
    menor_id = _menor_egresado(client, h_admin, hogar_id)
    client.post(f"/api/v1/archivo/menores/{menor_id}/cerrar", json={"motivo": "cierre"}, headers=h_admin)

    h_auditor = auth_header(client, session_factory, "auditor_arch6@prueba.local", "auditor")

    r = client.get(f"/api/v1/archivo/menores/{menor_id}", headers=h_auditor)
    assert r.status_code == 200
    assert r.json()["estado"] == "archivado"

    r = client.get(f"/api/v1/archivo/menores/{menor_id}/paquete", headers=h_auditor)
    assert r.status_code == 403

    # El auditor tampoco puede iniciar el cierre.
    menor_id_2 = _menor_egresado(client, h_admin, hogar_id)
    r = client.post(f"/api/v1/archivo/menores/{menor_id_2}/cerrar", json={"motivo": "cierre"}, headers=h_auditor)
    assert r.status_code == 403


def test_listado_archivados_coordinador_acotado_a_su_zona(client, session_factory):
    zona_a, hogar_a = crear_zona_y_hogar(session_factory, nombre_zona="Zona A listado")
    zona_b, hogar_b = crear_zona_y_hogar(session_factory, nombre_zona="Zona B listado")
    h_admin = auth_header(client, session_factory, "admin_arch7@prueba.local", "admin")

    menor_a = _menor_egresado(client, h_admin, hogar_a)
    menor_b = _menor_egresado(client, h_admin, hogar_b)
    client.post(f"/api/v1/archivo/menores/{menor_a}/cerrar", json={"motivo": "cierre a"}, headers=h_admin)
    client.post(f"/api/v1/archivo/menores/{menor_b}/cerrar", json={"motivo": "cierre b"}, headers=h_admin)

    h_coord_a = auth_header(client, session_factory, "coord_arch7@prueba.local", "coordinador", zona_id=zona_a)

    r = client.get("/api/v1/archivo", headers=h_coord_a)
    assert r.status_code == 200
    menores_listados = {e["menor_id"] for e in r.json()}
    assert menor_a in menores_listados
    assert menor_b not in menores_listados

    # Pedir explícitamente la zona ajena se deniega en vez de ignorarse en silencio.
    r = client.get("/api/v1/archivo", params={"zona_id": zona_b}, headers=h_coord_a)
    assert r.status_code == 403

    r_admin = client.get("/api/v1/archivo", headers=h_admin)
    assert r_admin.status_code == 200
    menores_admin = {e["menor_id"] for e in r_admin.json()}
    assert {menor_a, menor_b} <= menores_admin


def test_auditor_no_puede_listar_archivados(client, session_factory):
    """ADR-0010, sección 3.5: a diferencia de los otros tres endpoints, el listado no menciona
    `auditor`; se deniega por defecto."""
    h_auditor = auth_header(client, session_factory, "auditor_arch8@prueba.local", "auditor")
    r = client.get("/api/v1/archivo", headers=h_auditor)
    assert r.status_code == 403


def test_bloqueo_escritura_tras_archivar_documentos_alertas_citas(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_arch9@prueba.local", "admin")
    menor_id = _menor_egresado(client, h_admin, hogar_id)

    # Antes de archivar: la madre ya no tiene asignación vigente (se cerró), así que se prueba
    # el bloqueo con admin/migración, que sin el expediente archivado sí podría crear.
    r = client.post(
        "/api/v1/documentos",
        data={
            "menor_id": menor_id,
            "categoria": "identidad",
            "titulo": "Registro migrado",
            "migracion": "true",
            "motivo": "migración histórica",
        },
        files={"archivo": ("doc.txt", b"contenido previo al archivo", "text/plain")},
        headers=h_admin,
    )
    assert r.status_code == 201

    client.post(f"/api/v1/archivo/menores/{menor_id}/cerrar", json={"motivo": "cierre"}, headers=h_admin)

    r = client.post(
        "/api/v1/documentos",
        data={
            "menor_id": menor_id,
            "categoria": "identidad",
            "titulo": "Registro posterior",
            "migracion": "true",
            "motivo": "migración histórica",
        },
        files={"archivo": ("doc2.txt", b"contenido posterior al archivo", "text/plain")},
        headers=h_admin,
    )
    assert r.status_code == 403

    r = client.post(
        "/api/v1/alertas/evasion", json={"menor_id": menor_id, "descripcion": "intento tras archivo"}, headers=h_admin
    )
    assert r.status_code == 403

    r = client.post(
        "/api/v1/citas",
        json={"menor_id": menor_id, "tipo": "medica", "fecha_hora": "2030-01-01T10:00:00Z"},
        headers=h_admin,
    )
    assert r.status_code == 403
