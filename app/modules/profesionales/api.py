from fastapi import APIRouter

router = APIRouter(prefix="/profesionales", tags=["Profesionales"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "profesionales", "estado": "pendiente"}
