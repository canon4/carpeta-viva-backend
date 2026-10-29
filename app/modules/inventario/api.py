from fastapi import APIRouter

router = APIRouter(prefix="/inventario", tags=["Inventario del Hogar"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "inventario", "estado": "pendiente"}
