from fastapi import APIRouter

router = APIRouter(prefix="/citas", tags=["Citas y Recordatorios"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "citas", "estado": "pendiente"}
