"""Escribe openapi.json: el contrato entre backend y frontend. Ejecutar tras cambiar endpoints."""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.main import create_app  # noqa: E402


def generar() -> str:
    return json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    (RAIZ / "openapi.json").write_text(generar(), encoding="utf-8")
    print("openapi.json actualizado")
