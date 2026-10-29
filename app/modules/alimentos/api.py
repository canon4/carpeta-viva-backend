from fastapi import APIRouter

router = APIRouter(prefix="/alimentos", tags=["Control de Alimentos"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "alimentos", "estado": "pendiente"}
