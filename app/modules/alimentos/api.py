import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.models import Usuario

from .application import actualizar_alimento, crear_alimento, listar_alimentos, marcar_consumido
from .schemas import AlimentoItemCreate, AlimentoItemOut, AlimentoItemUpdate

router = APIRouter(prefix="/alimentos", tags=["Control de Alimentos"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "alimentos", "estado": "activo"}


@router.post("", response_model=AlimentoItemOut, status_code=status.HTTP_201_CREATED, summary="Registrar ingreso de alimento")
def crear_alimento_endpoint(
    datos: AlimentoItemCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> AlimentoItemOut:
    try:
        return crear_alimento(session, usuario, datos)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("", response_model=list[AlimentoItemOut], summary="Listar alimentos de un hogar")
def listar_alimentos_endpoint(
    hogar_id: uuid.UUID,
    perecedero: bool | None = None,
    consumido: bool | None = None,
    vencidos: bool | None = None,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> list[AlimentoItemOut]:
    return listar_alimentos(session, usuario, hogar_id, perecedero=perecedero, consumido=consumido, vencidos=vencidos)


@router.put("/{item_id}", response_model=AlimentoItemOut, summary="Actualizar alimento")
def actualizar_alimento_endpoint(
    item_id: uuid.UUID,
    datos: AlimentoItemUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> AlimentoItemOut:
    try:
        return actualizar_alimento(session, usuario, item_id, datos)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.put("/{item_id}/consumido", response_model=AlimentoItemOut, summary="Marcar alimento como consumido")
def marcar_consumido_endpoint(
    item_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> AlimentoItemOut:
    return marcar_consumido(session, usuario, item_id)
