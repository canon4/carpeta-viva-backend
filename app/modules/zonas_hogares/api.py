import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import requiere_roles
from app.modules.auth.domain import Rol
from app.modules.auth.models import Usuario

from .application import (
    actualizar_hogar,
    actualizar_zona,
    crear_hogar,
    crear_zona,
    listar_hogares,
    listar_zonas,
    obtener_hogar,
    obtener_zona,
)
from .schemas import HogarCreate, HogarOut, HogarUpdate, ZonaCreate, ZonaOut, ZonaUpdate

router = APIRouter(prefix="/zonas-hogares", tags=["Zonas y Hogares"])

_coordinador_o_admin = requiere_roles(Rol.COORDINADOR, Rol.ADMIN)


@router.post("/zonas", response_model=ZonaOut, status_code=status.HTTP_201_CREATED, summary="Crear zona")
def crear_zona_endpoint(
    datos: ZonaCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(_coordinador_o_admin)
) -> ZonaOut:
    return crear_zona(session, datos, usuario.id)


@router.get("/zonas", response_model=list[ZonaOut], summary="Listar zonas")
def listar_zonas_endpoint(
    session: Session = Depends(get_session), _=Depends(_coordinador_o_admin)
) -> list[ZonaOut]:
    return listar_zonas(session)


@router.get("/zonas/{zona_id}", response_model=ZonaOut, summary="Obtener zona")
def obtener_zona_endpoint(
    zona_id: uuid.UUID, session: Session = Depends(get_session), _=Depends(_coordinador_o_admin)
) -> ZonaOut:
    return obtener_zona(session, zona_id)


@router.put("/zonas/{zona_id}", response_model=ZonaOut, summary="Actualizar zona")
def actualizar_zona_endpoint(
    zona_id: uuid.UUID,
    datos: ZonaUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(_coordinador_o_admin),
) -> ZonaOut:
    return actualizar_zona(session, zona_id, datos, usuario.id)


@router.post("/hogares", response_model=HogarOut, status_code=status.HTTP_201_CREATED, summary="Crear hogar sustituto")
def crear_hogar_endpoint(
    datos: HogarCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(_coordinador_o_admin)
) -> HogarOut:
    try:
        return crear_hogar(session, datos, usuario.id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/hogares", response_model=list[HogarOut], summary="Listar hogares sustitutos")
def listar_hogares_endpoint(
    zona_id: uuid.UUID | None = None,
    session: Session = Depends(get_session),
    _=Depends(_coordinador_o_admin),
) -> list[HogarOut]:
    return listar_hogares(session, zona_id)


@router.get("/hogares/{hogar_id}", response_model=HogarOut, summary="Obtener hogar sustituto")
def obtener_hogar_endpoint(
    hogar_id: uuid.UUID, session: Session = Depends(get_session), _=Depends(_coordinador_o_admin)
) -> HogarOut:
    return obtener_hogar(session, hogar_id)


@router.put("/hogares/{hogar_id}", response_model=HogarOut, summary="Actualizar hogar sustituto")
def actualizar_hogar_endpoint(
    hogar_id: uuid.UUID,
    datos: HogarUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(_coordinador_o_admin),
) -> HogarOut:
    try:
        return actualizar_hogar(session, hogar_id, datos, usuario.id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "zonas_hogares", "estado": "activo"}
