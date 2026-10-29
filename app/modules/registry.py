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
    "reportes",
    "ia",
    "auditoria",
    "archivo",
]


def routers() -> list[APIRouter]:
    return [import_module(f"app.modules.{m}.api").router for m in MODULOS]
