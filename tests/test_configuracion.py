"""Configuración administrable (ADR-0013): catálogos y parámetros editables por `admin`."""
from app.core.security import hash_password
from app.modules.auth.models import Usuario

from .conftest import CLAVE_SINTETICA


def crear_usuario(session_factory, email, rol):
    with session_factory() as s:
        s.add(Usuario(email=email, password_hash=hash_password(CLAVE_SINTETICA), rol=rol))
        s.commit()


def login(client, email, password=CLAVE_SINTETICA):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


def auth_header(client, session_factory, email, rol):
    crear_usuario(session_factory, email, rol)
    token = login(client, email)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------

def test_admin_lista_grupos_de_catalogo(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    r = client.get("/api/v1/configuracion/catalogos", headers=h)
    assert r.status_code == 200
    grupos = {g["grupo"] for g in r.json()}
    assert {"categoria_documento_menor", "categoria_documento_hogar"} <= grupos
    menor = next(g for g in r.json() if g["grupo"] == "categoria_documento_menor")
    assert menor["con_seccion_acceso"] is True
    assert menor["total_opciones_activas"] >= 7


def test_lectura_publica_de_catalogo_no_exige_admin(client, session_factory):
    h = auth_header(client, session_factory, "madre1@prueba.local", "madre")
    r = client.get("/api/v1/configuracion/catalogos/categoria_documento_menor", headers=h)
    assert r.status_code == 200
    valores = {o["valor"] for o in r.json()}
    assert "salud" in valores
    # No expone metadatos de administración (id, seccion_acceso, activo).
    assert "seccion_acceso" not in r.json()[0]


def test_lectura_publica_de_catalogo_sin_token_es_401(client):
    assert client.get("/api/v1/configuracion/catalogos/categoria_documento_menor").status_code == 401


def test_admin_crea_opcion_en_grupo_con_seccion_exige_seccion_acceso(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    r = client.post(
        "/api/v1/configuracion/catalogos/categoria_documento_menor",
        json={"valor": "antecedentes_judiciales", "etiqueta": "Antecedentes judiciales", "orden": 10},
        headers=h,
    )
    # Omitir el campo por completo (no enviarlo) se rechaza: ADR-0013 sección 5.1 exige que el
    # admin elija explícitamente, aunque la elección sea básica. "No enviado" y "enviado como
    # null" son casos distintos (ver el siguiente test).
    assert r.status_code == 400


def test_admin_crea_opcion_en_grupo_con_seccion_null_explicito_es_basica(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    r = client.post(
        "/api/v1/configuracion/catalogos/categoria_documento_menor",
        json={"valor": "antecedentes_judiciales", "etiqueta": "Antecedentes judiciales", "seccion_acceso": None},
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["seccion_acceso"] is None


def test_admin_crea_opcion_con_seccion_fuera_de_conjunto_cerrado_es_400(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    r = client.post(
        "/api/v1/configuracion/catalogos/categoria_documento_menor",
        json={"valor": "nueva_cat", "etiqueta": "Nueva", "seccion_acceso": "texto_libre_invalido"},
        headers=h,
    )
    assert r.status_code == 400


def test_admin_crea_opcion_en_grupo_desconocido_es_400(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    r = client.post(
        "/api/v1/configuracion/catalogos/grupo_inexistente",
        json={"valor": "x", "etiqueta": "X"},
        headers=h,
    )
    assert r.status_code == 400


def test_admin_crea_opcion_con_seccion_sensible_queda_guardada(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    r = client.post(
        "/api/v1/configuracion/catalogos/categoria_documento_menor",
        json={"valor": "informe_forense", "etiqueta": "Informe forense", "seccion_acceso": "salud"},
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["seccion_acceso"] == "salud"


def test_put_no_permite_cambiar_seccion_acceso(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    client.post(
        "/api/v1/configuracion/catalogos/categoria_documento_menor",
        json={"valor": "con_seccion", "etiqueta": "Con sección", "seccion_acceso": "salud"},
        headers=h,
    )
    r = client.put(
        "/api/v1/configuracion/catalogos/categoria_documento_menor/con_seccion",
        json={"etiqueta": "Editada", "seccion_acceso": "psicosocial"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["etiqueta"] == "Editada"
    # seccion_acceso no cambió, aunque se envió en el payload (el esquema de PUT no lo acepta).
    assert r.json()["seccion_acceso"] == "salud"


def test_put_desactiva_opcion(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    client.post(
        "/api/v1/configuracion/catalogos/categoria_documento_hogar",
        json={"valor": "contrato_arriendo", "etiqueta": "Contrato de arriendo"},
        headers=h,
    )
    r = client.put(
        "/api/v1/configuracion/catalogos/categoria_documento_hogar/contrato_arriendo",
        json={"activo": False},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["activo"] is False

    r = client.get("/api/v1/configuracion/catalogos/categoria_documento_hogar", headers=h)
    assert all(o["valor"] != "contrato_arriendo" for o in r.json())


def test_no_admin_recibe_403_al_crear_opcion(client, session_factory):
    h = auth_header(client, session_factory, "madre1@prueba.local", "madre")
    r = client.post(
        "/api/v1/configuracion/catalogos/categoria_documento_hogar",
        json={"valor": "x", "etiqueta": "X"},
        headers=h,
    )
    assert r.status_code == 403


def test_no_admin_recibe_403_al_editar_opcion(client, session_factory):
    h_admin = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    client.post(
        "/api/v1/configuracion/catalogos/categoria_documento_hogar",
        json={"valor": "otra", "etiqueta": "Otra"},
        headers=h_admin,
    )
    h_madre = auth_header(client, session_factory, "madre1@prueba.local", "madre")
    r = client.put(
        "/api/v1/configuracion/catalogos/categoria_documento_hogar/otra",
        json={"activo": False},
        headers=h_madre,
    )
    assert r.status_code == 403


def test_no_admin_recibe_403_al_listar_admin(client, session_factory):
    h = auth_header(client, session_factory, "madre1@prueba.local", "madre")
    r = client.get("/api/v1/configuracion/catalogos/categoria_documento_menor/admin", headers=h)
    assert r.status_code == 403


def test_no_admin_recibe_403_al_listar_grupos(client, session_factory):
    h = auth_header(client, session_factory, "madre1@prueba.local", "madre")
    assert client.get("/api/v1/configuracion/catalogos", headers=h).status_code == 403


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

def test_admin_lista_parametros_con_valores_por_defecto(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    r = client.get("/api/v1/configuracion/parametros", headers=h)
    assert r.status_code == 200
    claves = {p["clave"] for p in r.json()}
    assert {"telefono_policia_infancia", "nombre_operador", "contacto_operador"} <= claves
    telefono = next(p for p in r.json() if p["clave"] == "telefono_policia_infancia")
    assert telefono["editado_por_admin"] is False
    assert telefono["valor_actual"] == telefono["valor_por_defecto"]


def test_admin_actualiza_parametro_y_queda_marcado_como_editado(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    r = client.put(
        "/api/v1/configuracion/parametros/telefono_policia_infancia",
        json={"valor": "123-editado"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["valor_actual"] == "123-editado"
    assert r.json()["editado_por_admin"] is True

    r = client.get("/api/v1/configuracion/parametros/telefono_policia_infancia", headers=h)
    assert r.json()["valor_actual"] == "123-editado"


def test_actualizar_parametro_desconocido_es_400(client, session_factory):
    h = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    r = client.put(
        "/api/v1/configuracion/parametros/clave_inexistente", json={"valor": "x"}, headers=h
    )
    assert r.status_code == 400


def test_no_admin_recibe_403_en_parametros(client, session_factory):
    h = auth_header(client, session_factory, "madre1@prueba.local", "madre")
    assert client.get("/api/v1/configuracion/parametros", headers=h).status_code == 403
    assert (
        client.put(
            "/api/v1/configuracion/parametros/telefono_policia_infancia",
            json={"valor": "x"},
            headers=h,
        ).status_code
        == 403
    )


def test_parametros_publicos_no_exige_admin_y_solo_muestra_publicos(client, session_factory):
    h = auth_header(client, session_factory, "madre1@prueba.local", "madre")
    r = client.get("/api/v1/configuracion/publica", headers=h)
    assert r.status_code == 200
    claves = {p["clave"] for p in r.json()}
    assert "nombre_operador" in claves
    assert "contacto_operador" in claves
    assert "telefono_policia_infancia" not in claves


def test_parametros_publicos_sin_token_es_401(client):
    assert client.get("/api/v1/configuracion/publica").status_code == 401


# ---------------------------------------------------------------------------
# Integración con `documentos` (ADR-0013, consecuencias): categoría inválida rechazada.
# ---------------------------------------------------------------------------

def test_telefono_policia_infancia_llega_a_alertas_evasion(client, session_factory):
    """`alertas.application._telefono_policia_infancia` ahora delega en
    `configuracion.application.obtener_parametro`."""
    from tests._helpers import (
        asignar_profesional_a_menor,
        auth_header as alertas_auth_header,
        crear_profesional,
    )

    h_admin = auth_header(client, session_factory, "admin1@prueba.local", "admin")
    client.put(
        "/api/v1/configuracion/parametros/telefono_policia_infancia",
        json={"valor": "300-policia"},
        headers=h_admin,
    )

    h_defensor = alertas_auth_header(client, session_factory, "defensor-conf@prueba.local", "defensor")
    uid_defensor = _usuario_id(session_factory, "defensor-conf@prueba.local")
    defensor_id = crear_profesional(session_factory, uid_defensor, "defensor")

    import datetime as _dt
    import uuid as _uuid

    from app.modules.menores.models import Menor

    with session_factory() as s:
        menor = Menor(
            nombres="Prueba",
            apellidos="Sintética",
            fecha_nacimiento=_dt.date(2015, 5, 1),
            tipo_documento="registro_civil",
            numero_documento=f"doc-{_uuid.uuid4().hex[:8]}",
        )
        s.add(menor)
        s.commit()
        menor_id = str(menor.id)

    asignar_profesional_a_menor(session_factory, menor_id, defensor_id, "defensor")

    r = client.post(
        "/api/v1/alertas/evasion",
        json={"menor_id": menor_id, "descripcion": "Prueba de integración"},
        headers=h_defensor,
    )
    assert r.status_code == 200
    assert r.json()["contactos_emergencia"]["policia_infancia_telefono"] == "300-policia"


def _usuario_id(session_factory, email):
    with session_factory() as s:
        from sqlalchemy import select

        usuario = s.scalars(select(Usuario).where(Usuario.email == email)).first()
        return str(usuario.id)
