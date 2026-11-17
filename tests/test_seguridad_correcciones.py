"""Correcciones de la revisión de seguridad del 17-11-2026 (ADR-0016).

1. Coordinador acotado a su zona en zonas, hogares, madres y traslados.
2. Tipo de archivo decidido por los bytes, no por el `Content-Type` del cliente.
3. Auditor sin resumen de IA de documentos.
4. Bloqueo por intentos fallidos, cambio de contraseña y revocación de tokens.
5. `login_fallido` no guarda el texto escrito en el campo de correo.
"""
from sqlalchemy import select

from app.core.tipos_archivo import detectar_tipo
from app.modules.auditoria.models import AuditoriaAcceso

from ._helpers import (
    CLAVE_SINTETICA,
    auth_header,
    crear_madre,
    crear_usuario,
    crear_zona_y_hogar,
    login,
    vincular_hogar_madre,
)
from .test_inventario import _item_recibido_de_madre

API = "/api/v1"
MENOR = {"nombres": "Lucía Prueba", "apellidos": "Sintética", "fecha_nacimiento": "2015-05-05"}


# ---------------------------------------------------------------------------
# 1. Zona del coordinador
# ---------------------------------------------------------------------------

def test_solo_admin_crea_zonas(client, session_factory):
    h_coord = auth_header(client, session_factory, "coordz1@prueba.local", "coordinador")
    assert client.post(f"{API}/zonas-hogares/zonas", json={"nombre": "Zona X"}, headers=h_coord).status_code == 403
    h_admin = auth_header(client, session_factory, "adminz1@prueba.local", "admin")
    assert client.post(f"{API}/zonas-hogares/zonas", json={"nombre": "Zona X"}, headers=h_admin).status_code == 201


def test_coordinador_solo_ve_y_edita_hogares_de_su_zona(client, session_factory):
    zona_a, hogar_a = crear_zona_y_hogar(session_factory, "Zona A")
    zona_b, hogar_b = crear_zona_y_hogar(session_factory, "Zona B")
    h = auth_header(client, session_factory, "coordz2@prueba.local", "coordinador", zona_a)

    zonas = client.get(f"{API}/zonas-hogares/zonas", headers=h).json()
    assert [z["id"] for z in zonas] == [zona_a]
    assert client.get(f"{API}/zonas-hogares/zonas/{zona_b}", headers=h).status_code == 403

    hogares = client.get(f"{API}/zonas-hogares/hogares", headers=h).json()
    assert {x["id"] for x in hogares} == {hogar_a}
    assert client.get(f"{API}/zonas-hogares/hogares?zona_id={zona_b}", headers=h).status_code == 403
    assert client.get(f"{API}/zonas-hogares/hogares/{hogar_b}", headers=h).status_code == 403
    assert client.put(f"{API}/zonas-hogares/hogares/{hogar_b}", json={"estado": "suspendido"}, headers=h).status_code == 403
    assert client.post(f"{API}/zonas-hogares/hogares", json={"zona_id": zona_b}, headers=h).status_code == 403
    assert client.post(f"{API}/zonas-hogares/hogares", json={"zona_id": zona_a}, headers=h).status_code == 201

    with session_factory() as s:
        acciones = {a.accion for a in s.scalars(select(AuditoriaAcceso))}
    assert "hogar_actualizacion_denegado" in acciones


def test_no_se_puede_reasignar_una_madre_de_otro_hogar(client, session_factory):
    zona_a, hogar_a = crear_zona_y_hogar(session_factory, "Zona A2")
    _, hogar_b = crear_zona_y_hogar(session_factory, "Zona B2")
    madre_b = crear_madre(session_factory, None, "900-1")
    vincular_hogar_madre(session_factory, hogar_b, madre_b)
    h = auth_header(client, session_factory, "coordz3@prueba.local", "coordinador", zona_a)

    r = client.put(f"{API}/zonas-hogares/hogares/{hogar_a}", json={"madre_id": madre_b}, headers=h)
    assert r.status_code == 422


def test_coordinador_solo_ve_madres_de_su_zona_o_sin_hogar(client, session_factory):
    zona_a, hogar_a = crear_zona_y_hogar(session_factory, "Zona A3")
    _, hogar_b = crear_zona_y_hogar(session_factory, "Zona B3")
    madre_a = crear_madre(session_factory, None, "901-1")
    madre_b = crear_madre(session_factory, None, "901-2")
    madre_libre = crear_madre(session_factory, None, "901-3")
    vincular_hogar_madre(session_factory, hogar_a, madre_a)
    vincular_hogar_madre(session_factory, hogar_b, madre_b)
    h = auth_header(client, session_factory, "coordz4@prueba.local", "coordinador", zona_a)

    ids = {m["id"] for m in client.get(f"{API}/madres", headers=h).json()}
    assert ids == {madre_a, madre_libre}
    assert client.get(f"{API}/madres/{madre_b}", headers=h).status_code == 403
    assert client.put(f"{API}/madres/{madre_b}", json={"telefono": "000"}, headers=h).status_code == 403


def test_coordinador_no_trae_a_su_zona_un_nna_de_otra_zona(client, session_factory):
    _, hogar_otra = crear_zona_y_hogar(session_factory, "Zona origen ajena")
    zona_propia, hogar_propio = crear_zona_y_hogar(session_factory, "Zona propia")
    h_admin = auth_header(client, session_factory, "adminz5@prueba.local", "admin")
    menor_id = client.post(f"{API}/menores", json=MENOR, headers=h_admin).json()["id"]
    r = client.post(
        f"{API}/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_otra, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )
    assert r.status_code == 201

    h = auth_header(client, session_factory, "coordz5@prueba.local", "coordinador", zona_propia)
    r = client.post(
        f"{API}/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_propio, "fecha_inicio": "2026-02-01", "tipo_movimiento": "traslado"},
        headers=h,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 2. Tipo de archivo por bytes
# ---------------------------------------------------------------------------

def test_detectar_tipo_por_firma():
    assert detectar_tipo(b"%PDF-1.4 x") == "application/pdf"
    assert detectar_tipo(b"\xff\xd8\xff\xe0x") == "image/jpeg"
    assert detectar_tipo(b"MZ\x90\x00ejecutable") is None
    assert detectar_tipo(b"\x7fELF binario") is None
    assert detectar_tipo(b"#!/bin/sh\nrm -rf /") is None
    assert detectar_tipo(b"PK\x03\x04no es un zip valido") is None
    assert detectar_tipo("Reporte diario sintético".encode()) == "text/plain"
    assert detectar_tipo(b"a,b\n1,2\n", "datos.csv") == "text/csv"


def _menor_de_admin(client, session_factory, email):
    h = auth_header(client, session_factory, email, "admin")
    return h, client.post(f"{API}/menores", json=MENOR, headers=h).json()["id"]


def _subir(client, h, menor_id, nombre, contenido, tipo):
    return client.post(
        f"{API}/documentos",
        data={"menor_id": menor_id, "categoria": "identidad", "titulo": "Prueba", "migracion": "true", "motivo": "migración"},
        files={"archivo": (nombre, contenido, tipo)},
        headers=h,
    )


def test_documento_ejecutable_declarado_como_imagen_es_422(client, session_factory):
    h, menor_id = _menor_de_admin(client, session_factory, "admind1@prueba.local")
    r = _subir(client, h, menor_id, "foto.jpg", b"MZ\x90\x00\x03\x00ejecutable sintetico", "image/jpeg")
    assert r.status_code == 422


def test_documento_guarda_el_tipo_real_no_el_declarado(client, session_factory):
    h, menor_id = _menor_de_admin(client, session_factory, "admind2@prueba.local")
    r = _subir(client, h, menor_id, "registro.jpg", b"%PDF-1.4 registro civil sintetico", "image/jpeg")
    assert r.status_code == 201
    assert r.json()["mime_type"] == "application/pdf"


def test_foto_de_inventario_con_bytes_no_imagen_es_422(client, session_factory):
    _, item_id, h_madre = _item_recibido_de_madre(client, session_factory, "Zona fotoseg", "madre_fotoseg@prueba.local", "fseg-1")
    r = client.post(
        f"{API}/inventario/items/{item_id}/fotos",
        files={"archivo": ("evidencia.jpg", b"MZ\x90\x00ejecutable", "image/jpeg")},
        data={"declaracion_sin_menores": "true"},
        headers=h_madre,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 3. Auditor sin resumen de IA de documentos
# ---------------------------------------------------------------------------

def test_auditor_no_obtiene_resumen_de_documento(client, session_factory):
    h, menor_id = _menor_de_admin(client, session_factory, "admini1@prueba.local")
    doc_id = _subir(client, h, menor_id, "doc.txt", "Contenido sintético".encode(), "text/plain").json()["id"]
    h_aud = auth_header(client, session_factory, "auditor1@prueba.local", "auditor")
    assert client.get(f"{API}/ia/documentos/{doc_id}/resumen", headers=h_aud).status_code == 403


# ---------------------------------------------------------------------------
# 4 y 5. Cuentas
# ---------------------------------------------------------------------------

def _login(client, email, password):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


def test_bloqueo_tras_intentos_fallidos(client, session_factory):
    crear_usuario(session_factory, "bloqueo@prueba.local", "madre")
    for _ in range(4):
        assert _login(client, "bloqueo@prueba.local", "mala").status_code == 401
    assert _login(client, "bloqueo@prueba.local", "mala").status_code == 429
    # Bloqueada: ni siquiera la clave correcta entra mientras dure el bloqueo.
    assert _login(client, "bloqueo@prueba.local", CLAVE_SINTETICA).status_code == 429


def test_login_correcto_reinicia_el_contador(client, session_factory):
    crear_usuario(session_factory, "contador@prueba.local", "madre")
    for _ in range(4):
        _login(client, "contador@prueba.local", "mala")
    assert _login(client, "contador@prueba.local", CLAVE_SINTETICA).status_code == 200
    for _ in range(4):
        assert _login(client, "contador@prueba.local", "mala").status_code == 401


def test_login_fallido_no_guarda_lo_escrito_en_el_correo(client, session_factory):
    _login(client, "mi-clave-secreta-tecleada-por-error", "x")
    with session_factory() as s:
        fallidos = list(s.scalars(select(AuditoriaAcceso).where(AuditoriaAcceso.accion == "login_fallido")))
    assert fallidos
    assert all(f.recurso is None for f in fallidos)


def test_cambio_de_contrasena_revoca_tokens_anteriores(client, session_factory):
    crear_usuario(session_factory, "cambio@prueba.local", "madre")
    token_viejo = login(client, "cambio@prueba.local")
    h_viejo = {"Authorization": f"Bearer {token_viejo}"}

    r = client.put(f"{API}/auth/contrasena", json={"actual": "mala", "nueva": "nueva-clave-segura"}, headers=h_viejo)
    assert r.status_code == 422
    r = client.put(f"{API}/auth/contrasena", json={"actual": CLAVE_SINTETICA, "nueva": "corta"}, headers=h_viejo)
    assert r.status_code == 422
    r = client.put(
        f"{API}/auth/contrasena", json={"actual": CLAVE_SINTETICA, "nueva": "nueva-clave-segura"}, headers=h_viejo
    )
    assert r.status_code == 200
    token_nuevo = r.json()["access_token"]

    assert _login(client, "cambio@prueba.local", CLAVE_SINTETICA).status_code == 401
    assert _login(client, "cambio@prueba.local", "nueva-clave-segura").status_code == 200
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token_nuevo}"}).status_code == 200


def test_token_emitido_antes_del_cambio_queda_revocado():
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace

    from app.modules.auth.application import token_revocado

    cambio = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)
    usuario = SimpleNamespace(credenciales_cambiadas_en=cambio)
    assert token_revocado(usuario, int((cambio - timedelta(minutes=5)).timestamp()))
    assert not token_revocado(usuario, int(cambio.timestamp()))
    assert not token_revocado(SimpleNamespace(credenciales_cambiadas_en=None), 0)
