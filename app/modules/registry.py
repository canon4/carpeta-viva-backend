from importlib import import_module

from fastapi import APIRouter

MODULOS = [
    "auth",
    "zonas_hogares",
    "madres",
    "profesionales",
    "menores",
    "asignaciones",
    "documentos",
    "inventario",
    "alimentos",
    "citas",
    "alertas",
    "configuracion",
    "reportes",
    "ia",
    "auditoria",
    "archivo",
]


def routers() -> list[APIRouter]:
    """Un router por módulo (1:1 con `MODULOS`, bajo su propio prefijo)."""
    return [import_module(f"app.modules.{m}.api").router for m in MODULOS]


def routers_extra() -> list[APIRouter]:
    """Routers adicionales que un módulo expone con otro prefijo (p. ej. `/usuarios/*` en
    `auth`, ADR-0019: directorio de personal, no autenticación propiamente). No participan en la
    correspondencia 1:1 de `routers()`/`MODULOS`."""
    resultado = []
    for nombre in MODULOS:
        modulo = import_module(f"app.modules.{nombre}.api")
        resultado.extend(getattr(modulo, "routers_extra", []))
    return resultado
