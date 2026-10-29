from fastapi import APIRouter

router = APIRouter(prefix="/menores", tags=["Menores y Expedientes"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "menores", "estado": "pendiente"}
