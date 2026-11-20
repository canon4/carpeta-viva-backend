"""Configuración del proveedor de IA editable por el admin (ADR-0017).

La clave se guarda cifrada, nunca se devuelve ni queda en auditoría, solo el admin la gestiona y
la clave del panel tiene prioridad sobre la del entorno.
"""
from sqlalchemy import select

from app.modules.auditoria.models import AuditoriaAcceso
from app.modules.ia.application import _configuracion_activa
from app.modules.ia.models import IaConfiguracion

from ._helpers import auth_header

API = "/api/v1/ia/configuracion"
CLAVE = "sk-sintetica-de-prueba-0123456789abcd"


def test_solo_admin_ve_y_cambia_la_configuracion(client, session_factory):
    h = auth_header(client, session_factory, "coord-ia@prueba.local", "coordinador")
    assert client.get(API, headers=h).status_code == 403
    assert client.put(API, json={"api_key": CLAVE}, headers=h).status_code == 403
    assert client.post(f"{API}/probar", headers=h).status_code == 403


def test_la_clave_se_guarda_cifrada_y_nunca_se_devuelve(client, session_factory):
    h = auth_header(client, session_factory, "admin-ia1@prueba.local", "admin")
    r = client.get(API, headers=h)
    assert r.status_code == 200
    assert r.json()["clave_origen"] == "ninguna"

    r = client.put(API, json={"proveedor": "anthropic", "modelo": "modelo-sintetico", "api_key": CLAVE}, headers=h)
    assert r.status_code == 200
    cuerpo = r.text
    assert CLAVE not in cuerpo
    assert r.json()["clave_origen"] == "panel"
    assert r.json()["clave_sufijo"] == CLAVE[-4:]
    assert r.json()["modelo"] == "modelo-sintetico"

    with session_factory() as s:
        fila = s.scalars(select(IaConfiguracion)).one()
        assert fila.api_key_cifrada and CLAVE not in fila.api_key_cifrada
        assert _configuracion_activa(s)[2] == CLAVE
        acciones = " ".join(a.accion + (a.recurso or "") for a in s.scalars(select(AuditoriaAcceso)))
    assert CLAVE not in acciones
    assert "ia_configuracion_actualizada" in acciones


def test_clave_vacia_vuelve_a_la_del_entorno(client, session_factory):
    h = auth_header(client, session_factory, "admin-ia2@prueba.local", "admin")
    client.put(API, json={"api_key": CLAVE}, headers=h)
    r = client.put(API, json={"api_key": ""}, headers=h)
    assert r.status_code == 200
    assert r.json()["clave_origen"] == "ninguna"
    assert r.json()["clave_sufijo"] is None


def test_valida_proveedor_y_clave(client, session_factory):
    h = auth_header(client, session_factory, "admin-ia3@prueba.local", "admin")
    assert client.put(API, json={"proveedor": "inventado"}, headers=h).status_code == 422
    assert client.put(API, json={"api_key": "corta"}, headers=h).status_code == 422
    assert client.put(API, json={"api_key": "clave con espacios en medio 123456"}, headers=h).status_code == 422


def test_cambiar_de_proveedor_descarta_la_clave_anterior(client, session_factory):
    h = auth_header(client, session_factory, "admin-ia4@prueba.local", "admin")
    client.put(API, json={"proveedor": "anthropic", "api_key": CLAVE}, headers=h)
    r = client.put(API, json={"proveedor": "groq", "modelo": "otro-modelo"}, headers=h)
    assert r.json()["clave_origen"] == "ninguna"


def test_probar_sin_clave_informa_el_error_sin_llamar_afuera(client, session_factory):
    h = auth_header(client, session_factory, "admin-ia5@prueba.local", "admin")
    r = client.post(f"{API}/probar", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_listar_modelos_solo_admin_y_sin_clave_informa_error(client, session_factory):
    h_coord = auth_header(client, session_factory, "coord-mod@prueba.local", "coordinador")
    assert client.get(f"{API}/modelos", headers=h_coord).status_code == 403
    h = auth_header(client, session_factory, "admin-mod@prueba.local", "admin")
    r = client.get(f"{API}/modelos", params={"proveedor": "groq"}, headers=h)
    assert r.status_code == 200
    assert r.json()["modelos"] == []
    assert r.json()["error"]
    assert client.get(f"{API}/modelos", params={"proveedor": "inventado"}, headers=h).status_code == 422


def test_listar_modelos_usa_la_clave_del_panel(client, session_factory, monkeypatch):
    import app.core.ia_llm as ia_llm

    vistas = {}

    def falso(proveedor, api_key):
        vistas["clave"] = api_key
        return ["modelo-a", "modelo-b"]

    monkeypatch.setattr(ia_llm, "listar_modelos", falso)
    h = auth_header(client, session_factory, "admin-mod2@prueba.local", "admin")
    client.put(API, json={"proveedor": "groq", "modelo": "x", "api_key": CLAVE}, headers=h)
    r = client.get(f"{API}/modelos", headers=h)
    assert r.json() == {"proveedor": "groq", "modelos": ["modelo-a", "modelo-b"], "error": None}
    assert vistas["clave"] == CLAVE
