from fastapi import APIRouter

router = APIRouter(prefix="/alertas", tags=["Alertas y Evasiones"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "alertas", "estado": "pendiente"}
