import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.models import Usuario

from .application import (
    actualizar_alimento,
    actualizar_checklist_item,
    comprar_de_checklist,
    crear_alimento,
    crear_checklist_item,
    listar_alimentos,
    listar_checklist_items,
    marcar_consumido,
)
from .schemas import (
    AlimentoChecklistComprar,
    AlimentoChecklistItemCreate,
    AlimentoChecklistItemOut,
    AlimentoChecklistItemUpdate,
    AlimentoItemCreate,
    AlimentoItemOut,
    AlimentoItemUpdate,
)

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


@router.post(
    "/checklist", response_model=AlimentoChecklistItemOut, status_code=status.HTTP_201_CREATED, summary="Crear producto reutilizable"
)
def crear_checklist_endpoint(
    datos: AlimentoChecklistItemCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> AlimentoChecklistItemOut:
    return crear_checklist_item(session, usuario, datos)


@router.get("/checklist", response_model=list[AlimentoChecklistItemOut], summary="Listar checklist de un hogar")
def listar_checklist_endpoint(
    hogar_id: uuid.UUID,
    incluir_inactivos: bool = False,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> list[AlimentoChecklistItemOut]:
    return listar_checklist_items(session, usuario, hogar_id, incluir_inactivos=incluir_inactivos)


@router.put("/checklist/{checklist_item_id}", response_model=AlimentoChecklistItemOut, summary="Actualizar producto del checklist")
def actualizar_checklist_endpoint(
    checklist_item_id: uuid.UUID,
    datos: AlimentoChecklistItemUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> AlimentoChecklistItemOut:
    return actualizar_checklist_item(session, usuario, checklist_item_id, datos)


@router.post(
    "/checklist/{checklist_item_id}/comprar",
    response_model=AlimentoItemOut,
    status_code=status.HTTP_201_CREATED,
    summary="Comprar de nuevo un producto del checklist",
)
def comprar_de_checklist_endpoint(
    checklist_item_id: uuid.UUID,
    datos: AlimentoChecklistComprar,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> AlimentoItemOut:
    try:
        return comprar_de_checklist(session, usuario, checklist_item_id, datos)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


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
