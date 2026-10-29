from fastapi import APIRouter

router = APIRouter(prefix="/zonas-hogares", tags=["Zonas y Hogares"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "zonas_hogares", "estado": "pendiente"}
