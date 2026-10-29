from fastapi import APIRouter

router = APIRouter(prefix="/reportes", tags=["Reportes"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "reportes", "estado": "pendiente"}
