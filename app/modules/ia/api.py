from fastapi import APIRouter

router = APIRouter(prefix="/ia", tags=["Asistente de IA"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "ia", "estado": "pendiente"}
