from fastapi import APIRouter

router = APIRouter(prefix="/archivo", tags=["Archivo y Cierre"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "archivo", "estado": "pendiente"}
