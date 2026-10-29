from fastapi import APIRouter

router = APIRouter(prefix="/madres", tags=["Madres Sustitutas"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "madres", "estado": "pendiente"}
