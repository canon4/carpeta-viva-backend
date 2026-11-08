"""Pruebas de Reportes (ADR-0010, sección 2): autorización por nivel, exportación y, sobre
todo, las dos correcciones obligatorias de seguridad: revalidar el permiso vigente al
descargar un informe exportado (no el que existía al generar) y la interacción con un
expediente archivado después de exportado."""
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
    "fecha_nacimiento": "2016-09-01",
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
        json={"fecha_fin": "2026-06-01", "motivo": "egreso"},
        headers=h_admin,
    )
    assert r.status_code == 200


def test_reporte_general_coordinador_limitado_a_su_zona(client, session_factory):
    zona_a, hogar_a = crear_zona_y_hogar(session_factory, nombre_zona="Zona general A")
    zona_b, hogar_b = crear_zona_y_hogar(session_factory, nombre_zona="Zona general B")
    h_admin = auth_header(client, session_factory, "admin_rep1@prueba.local", "admin")
    menor_a = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_a, hogar_a)
    menor_b = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_b, hogar_b)

    h_coord_a = auth_header(client, session_factory, "coord_rep1@prueba.local", "coordinador", zona_id=zona_a)
    r = client.get("/api/v1/reportes/general", headers=h_coord_a)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["zona_id"] == zona_a
    # Solo su zona: un único menor activo contado, no los dos del sistema.
    assert sum(cuerpo["menores_por_estado"].values()) == 1

    r_admin = client.get("/api/v1/reportes/general", headers=h_admin)
    assert r_admin.status_code == 200
    assert r_admin.json()["zona_id"] is None
    assert sum(r_admin.json()["menores_por_estado"].values()) == 2


def test_reporte_zona_denegado_a_coordinador_de_otra_zona(client, session_factory):
    zona_a, _hogar_a = crear_zona_y_hogar(session_factory, nombre_zona="Zona Z1")
    zona_b, _hogar_b = crear_zona_y_hogar(session_factory, nombre_zona="Zona Z2")
    h_coord_a = auth_header(client, session_factory, "coord_rep2@prueba.local", "coordinador", zona_id=zona_a)

    r = client.get(f"/api/v1/reportes/zona/{zona_b}", headers=h_coord_a)
    assert r.status_code == 403

    r = client.get(f"/api/v1/reportes/zona/{zona_a}", headers=h_coord_a)
    assert r.status_code == 200


def test_reporte_menor_secciones_sin_acceso_para_coordinador(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_rep3@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    h_coord = auth_header(client, session_factory, "coord_rep3@prueba.local", "coordinador", zona_id=zona_id)
    r = client.get(f"/api/v1/reportes/menor/{menor_id}", headers=h_coord)
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo["secciones_sin_acceso"]) == {"familia", "salud", "psicosocial"}


def test_reporte_menor_denegado_sin_relacion(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_rep4@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_ajena = crear_usuario(session_factory, "madre_ajena_rep4@prueba.local", "madre")
    crear_madre(session_factory, uid_ajena, "900-rep4")
    h_madre_ajena = {"Authorization": f"Bearer {login(client, 'madre_ajena_rep4@prueba.local')}"}

    r = client.get(f"/api/v1/reportes/menor/{menor_id}", headers=h_madre_ajena)
    assert r.status_code == 403


def test_reporte_madre_propia_vs_ajena_y_auditor_agregado(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_rep5@prueba.local", "admin")
    uid_madre = crear_usuario(session_factory, "madre_rep5@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-rep5")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_rep5@prueba.local')}"}

    r = client.get(f"/api/v1/reportes/madre/{madre_id}", headers=h_madre)
    assert r.status_code == 200
    assert r.json()["solo_agregado"] is False

    uid_otra = crear_usuario(session_factory, "madre_otra_rep5@prueba.local", "madre")
    h_otra = {"Authorization": f"Bearer {login(client, 'madre_otra_rep5@prueba.local')}"}
    r = client.get(f"/api/v1/reportes/madre/{madre_id}", headers=h_otra)
    assert r.status_code == 403

    h_auditor = auth_header(client, session_factory, "auditor_rep5@prueba.local", "auditor")
    r = client.get(f"/api/v1/reportes/madre/{madre_id}", headers=h_auditor)
    assert r.status_code == 200
    assert r.json()["solo_agregado"] is True


def test_exportar_y_descargar_json(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_rep6@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    r = client.post(
        "/api/v1/reportes/exportar",
        json={"nivel": "menor", "menor_id": menor_id, "formato": "json"},
        headers=h_admin,
    )
    assert r.status_code == 201
    informe_id = r.json()["id"]
    assert r.json()["filtros"]["menor_id"] == menor_id

    r = client.get("/api/v1/reportes/exportados", headers=h_admin)
    assert any(i["id"] == informe_id for i in r.json())

    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_admin)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")


def test_exportar_csv_y_pdf(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_rep7@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    for formato, prefijo_mime in (("csv", "text/csv"), ("pdf", "application/pdf")):
        r = client.post(
            "/api/v1/reportes/exportar",
            json={"nivel": "menor", "menor_id": menor_id, "formato": formato},
            headers=h_admin,
        )
        assert r.status_code == 201, r.text
        informe_id = r.json()["id"]
        r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_admin)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith(prefijo_mime)
        assert len(r.content) > 0


def test_revalidacion_al_descargar_tras_perder_la_asignacion(client, session_factory):
    """Corrección obligatoria (ADR-0010, sección 2): quien exportó con acceso vigente pierde el
    acceso después (egreso -> RF7 revoca permisos/asignación de la madre) y la descarga del
    informe ya generado debe denegarse, no servirse igual."""
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_rep8@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    asignacion_id = ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_madre = crear_usuario(session_factory, "madre_rep8@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-rep8")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_rep8@prueba.local')}"}

    r = client.post(
        "/api/v1/reportes/exportar",
        json={"nivel": "menor", "menor_id": menor_id, "formato": "json"},
        headers=h_madre,
    )
    assert r.status_code == 201
    informe_id = r.json()["id"]

    # Mientras la asignación está vigente, la madre descarga su propio informe sin problema.
    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_madre)
    assert r.status_code == 200

    cerrar_asignacion(client, h_admin, asignacion_id)

    # Ahora ya no tiene relación vigente con el menor: la descarga se revalida y se deniega,
    # aunque el archivo exportado siga existiendo igual que antes.
    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_madre)
    assert r.status_code == 403


def test_revalidacion_al_descargar_tras_revocar_permiso_de_seccion(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_rep9@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_madre = crear_usuario(session_factory, "madre_rep9@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-rep9")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)

    uid_defensor = crear_usuario(session_factory, "defensor_rep9@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_defensor, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    h_defensor = {"Authorization": f"Bearer {login(client, 'defensor_rep9@prueba.local')}"}
    r = client.post(
        f"/api/v1/menores/{menor_id}/permisos",
        json={"seccion": "salud", "usuario_id": uid_madre},
        headers=h_defensor,
    )
    permiso_id = r.json()["id"]
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_rep9@prueba.local')}"}

    r = client.post(
        "/api/v1/reportes/exportar",
        json={"nivel": "menor", "menor_id": menor_id, "formato": "json"},
        headers=h_madre,
    )
    informe_id = r.json()["id"]
    assert "salud" in r.json()["filtros"]["secciones_incluidas"]

    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_madre)
    assert r.status_code == 200

    client.delete(f"/api/v1/menores/{menor_id}/permisos/{permiso_id}", headers=h_defensor)

    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_madre)
    assert r.status_code == 403


def test_revalidacion_al_descargar_tras_archivar_el_expediente(client, session_factory):
    """Corrección obligatoria (ADR-0010, sección 2, último punto): si el menor incluido se
    archiva después de exportado, la descarga pasa a tratarse como contenido de expediente
    archivado (coordinador/admin de la zona archivada; el defensor que exportó con acceso
    vigente ya no puede)."""
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_rep10@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    asignacion_id = ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_defensor = crear_usuario(session_factory, "defensor_rep10@prueba.local", "defensor")
    profesional_id = crear_profesional(session_factory, uid_defensor, "defensor")
    asignar_profesional_a_menor(session_factory, menor_id, profesional_id, "defensor")
    h_defensor = {"Authorization": f"Bearer {login(client, 'defensor_rep10@prueba.local')}"}

    r = client.post(
        "/api/v1/reportes/exportar",
        json={"nivel": "menor", "menor_id": menor_id, "formato": "json"},
        headers=h_defensor,
    )
    assert r.status_code == 201
    informe_id = r.json()["id"]

    # Antes de archivar, el defensor asignado descarga sin problema.
    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_defensor)
    assert r.status_code == 200

    cerrar_asignacion(client, h_admin, asignacion_id)
    r = client.post(f"/api/v1/archivo/menores/{menor_id}/cerrar", json={"motivo": "cierre"}, headers=h_admin)
    assert r.status_code == 200

    # El defensor asignado ya no puede descargar: el expediente archivado restringe a
    # coordinador/admin de la zona archivada, igual que el paquete de archivo.
    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_defensor)
    assert r.status_code == 403

    h_coord = auth_header(client, session_factory, "coord_rep10@prueba.local", "coordinador", zona_id=zona_id)
    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_coord)
    assert r.status_code == 200

    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_admin)
    assert r.status_code == 200


def test_auditor_nunca_descarga_contenido_exportado(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_rep11@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    r = client.post(
        "/api/v1/reportes/exportar",
        json={"nivel": "general", "formato": "json"},
        headers=h_admin,
    )
    informe_id = r.json()["id"]

    h_auditor = auth_header(client, session_factory, "auditor_rep11@prueba.local", "auditor")
    r = client.get("/api/v1/reportes/exportados", headers=h_auditor)
    assert r.status_code == 200
    assert any(i["id"] == informe_id for i in r.json())

    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_auditor)
    assert r.status_code == 403


def test_revalidacion_al_descargar_general_acota_a_la_zona_del_coordinador(client, session_factory):
    """Hueco encontrado en revisión de cierre de Fase 5: `_autorizado_descarga_ahora` para el
    nivel "general" solo validaba el rol, no si el coordinador que descarga es de la misma zona
    que quedó congelada en `filtros["zona_id"]` al exportar. Sin este chequeo, el coordinador de
    una zona podía descargar el agregado "general" (ya acotado a otra zona al generarse) de un
    coordinador de una zona distinta, o incluso el agregado nacional (zona_id=None) de admin."""
    zona_a, _hogar_a = crear_zona_y_hogar(session_factory, nombre_zona="Zona general descarga A")
    zona_b, _hogar_b = crear_zona_y_hogar(session_factory, nombre_zona="Zona general descarga B")
    h_admin = auth_header(client, session_factory, "admin_rep13@prueba.local", "admin")
    h_coord_a = auth_header(client, session_factory, "coord_rep13a@prueba.local", "coordinador", zona_id=zona_a)
    h_coord_b = auth_header(client, session_factory, "coord_rep13b@prueba.local", "coordinador", zona_id=zona_b)

    r = client.post("/api/v1/reportes/exportar", json={"nivel": "general", "formato": "json"}, headers=h_coord_a)
    assert r.status_code == 201
    informe_id = r.json()["id"]
    assert r.json()["filtros"]["zona_id"] == zona_a

    # El propio coordinador que exportó (su zona) sí puede descargar.
    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_coord_a)
    assert r.status_code == 200

    # Un coordinador de otra zona no puede descargar el agregado ajeno.
    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_coord_b)
    assert r.status_code == 403

    # admin sí puede (sin restricción de zona).
    r = client.get(f"/api/v1/reportes/exportados/{informe_id}/contenido", headers=h_admin)
    assert r.status_code == 200

    # El agregado nacional de admin (zona_id=None) tampoco es descargable por un coordinador.
    r = client.post("/api/v1/reportes/exportar", json={"nivel": "general", "formato": "json"}, headers=h_admin)
    informe_nacional_id = r.json()["id"]
    assert r.json()["filtros"]["zona_id"] is None
    r = client.get(f"/api/v1/reportes/exportados/{informe_nacional_id}/contenido", headers=h_coord_a)
    assert r.status_code == 403


def test_listar_exportados_scope_por_usuario(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_rep12@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin)
    ingresar_menor(client, h_admin, menor_id, hogar_id)
    client.post(
        "/api/v1/reportes/exportar", json={"nivel": "menor", "menor_id": menor_id, "formato": "json"}, headers=h_admin
    )

    h_coord = auth_header(client, session_factory, "coord_rep12@prueba.local", "coordinador", zona_id=zona_id)
    r = client.get("/api/v1/reportes/exportados", headers=h_coord)
    assert r.status_code == 200
    assert r.json() == []  # el coordinador no generó ninguno propio

    r = client.get("/api/v1/reportes/exportados", headers=h_admin)
    assert len(r.json()) >= 1
