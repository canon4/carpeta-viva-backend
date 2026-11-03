import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.models import Usuario

from .application import (
    actualizar_conviviente,
    actualizar_item,
    actualizar_red_apoyo,
    crear_conviviente,
    crear_item,
    crear_red_apoyo,
    listar_convivientes,
    listar_items,
    listar_red_apoyo,
)
from .schemas import (
    ConvivienteCreate,
    ConvivienteOut,
    ConvivienteUpdate,
    InventarioItemCreate,
    InventarioItemOut,
    InventarioItemUpdate,
    RedApoyoCreate,
    RedApoyoOut,
    RedApoyoUpdate,
)

router = APIRouter(prefix="/inventario", tags=["Inventario del Hogar"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "inventario", "estado": "activo"}


# ---------------------------------------------------------------------------
# Items (camas, muebles, otro)
# ---------------------------------------------------------------------------

@router.post("/items", response_model=InventarioItemOut, status_code=status.HTTP_201_CREATED, summary="Crear ítem de inventario")
def crear_item_endpoint(
    datos: InventarioItemCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> InventarioItemOut:
    return crear_item(session, usuario, datos)


@router.get("/items", response_model=list[InventarioItemOut], summary="Listar ítems de inventario de un hogar")
def listar_items_endpoint(
    hogar_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[InventarioItemOut]:
    return listar_items(session, usuario, hogar_id)


@router.put("/items/{item_id}", response_model=InventarioItemOut, summary="Actualizar ítem de inventario")
def actualizar_item_endpoint(
    item_id: uuid.UUID,
    datos: InventarioItemUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> InventarioItemOut:
    return actualizar_item(session, usuario, item_id, datos)


# ---------------------------------------------------------------------------
# Convivientes
# ---------------------------------------------------------------------------

@router.post("/convivientes", response_model=ConvivienteOut, status_code=status.HTTP_201_CREATED, summary="Registrar conviviente")
def crear_conviviente_endpoint(
    datos: ConvivienteCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ConvivienteOut:
    return crear_conviviente(session, usuario, datos)


@router.get("/convivientes", response_model=list[ConvivienteOut], summary="Listar convivientes de un hogar")
def listar_convivientes_endpoint(
    hogar_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[ConvivienteOut]:
    return listar_convivientes(session, usuario, hogar_id)


@router.put("/convivientes/{conviviente_id}", response_model=ConvivienteOut, summary="Actualizar conviviente (incluye desactivar)")
def actualizar_conviviente_endpoint(
    conviviente_id: uuid.UUID,
    datos: ConvivienteUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> ConvivienteOut:
    return actualizar_conviviente(session, usuario, conviviente_id, datos)


# ---------------------------------------------------------------------------
# Red de apoyo
# ---------------------------------------------------------------------------

@router.post("/red-apoyo", response_model=RedApoyoOut, status_code=status.HTTP_201_CREATED, summary="Registrar contacto de red de apoyo")
def crear_red_apoyo_endpoint(
    datos: RedApoyoCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> RedApoyoOut:
    return crear_red_apoyo(session, usuario, datos)


@router.get("/red-apoyo", response_model=list[RedApoyoOut], summary="Listar red de apoyo de un hogar")
def listar_red_apoyo_endpoint(
    hogar_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[RedApoyoOut]:
    return listar_red_apoyo(session, usuario, hogar_id)


@router.put("/red-apoyo/{contacto_id}", response_model=RedApoyoOut, summary="Actualizar contacto de red de apoyo")
def actualizar_red_apoyo_endpoint(
    contacto_id: uuid.UUID,
    datos: RedApoyoUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> RedApoyoOut:
    return actualizar_red_apoyo(session, usuario, contacto_id, datos)
