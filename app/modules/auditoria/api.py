from fastapi import APIRouter

router = APIRouter(prefix="/auditoria", tags=["Auditoría"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "auditoria", "estado": "pendiente"}
