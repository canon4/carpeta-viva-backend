from fastapi import APIRouter

router = APIRouter(prefix="/documentos", tags=["Gestión Documental"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "documentos", "estado": "pendiente"}
