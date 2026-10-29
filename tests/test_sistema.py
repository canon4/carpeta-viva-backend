import json
from pathlib import Path

import pytest

from app.core import config
from app.main import create_app
from app.modules.registry import MODULOS, routers
from scripts.export_openapi import generar


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


@pytest.mark.parametrize("router", routers(), ids=MODULOS)
def test_cada_modulo_responde_estado(client, router):
    r = client.get(f"/api/v1{router.prefix}/_estado")
    assert r.status_code == 200
    assert "modulo" in r.json()


def test_hay_15_modulos():
    assert len(MODULOS) == 15


def test_contrato_openapi_esta_actualizado():
    guardado = Path(__file__).resolve().parents[1] / "openapi.json"
    assert guardado.exists(), "Falta openapi.json: ejecute scripts/export_openapi.py"
    assert json.loads(guardado.read_text(encoding="utf-8")) == json.loads(generar())


def test_produccion_exige_jwt_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    config.get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            create_app()
    finally:
        config.get_settings.cache_clear()
