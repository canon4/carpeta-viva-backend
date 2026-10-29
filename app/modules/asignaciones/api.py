from fastapi import APIRouter

router = APIRouter(prefix="/asignaciones", tags=["Asignaciones y Traslados"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "asignaciones", "estado": "pendiente"}
