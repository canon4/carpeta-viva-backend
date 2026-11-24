import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import requiere_roles, usuario_actual
from app.modules.auth.domain import Rol
from app.modules.auth.models import Usuario

from .application import (
    actualizar_madre,
    actualizar_mi_firma,
    actualizar_mi_perfil,
    crear_madre,
    listar_madres,
    obtener_madre,
    obtener_mi_perfil_con_hogar,
)
from .schemas import FirmaUpdate, MadreAutoUpdate, MadreCreate, MadreOut, MadreUpdate

router = APIRouter(prefix="/madres", tags=["Madres Sustitutas"])

_coordinador_o_admin = requiere_roles(Rol.COORDINADOR, Rol.ADMIN)
_madre = requiere_roles(Rol.MADRE)


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "madres", "estado": "activo"}


@router.get("/yo", response_model=MadreOut, summary="Perfil de la madre autenticada")
def mi_perfil(session: Session = Depends(get_session), usuario: Usuario = Depends(_madre)) -> MadreOut:
    return obtener_mi_perfil_con_hogar(session, usuario.id)


@router.put("/yo", response_model=MadreOut, summary="Actualizar mis datos básicos (dirección, teléfono)")
def actualizar_mi_perfil_endpoint(
    datos: MadreAutoUpdate, session: Session = Depends(get_session), usuario: Usuario = Depends(_madre)
) -> MadreOut:
    return actualizar_mi_perfil(session, usuario.id, datos)


@router.put("/yo/firma", response_model=MadreOut, summary="Cargar la firma de la madre autenticada")
def cargar_mi_firma(
    datos: FirmaUpdate, session: Session = Depends(get_session), usuario: Usuario = Depends(_madre)
) -> MadreOut:
    return actualizar_mi_firma(session, usuario.id, datos.firma_ref)


@router.post("", response_model=MadreOut, status_code=status.HTTP_201_CREATED, summary="Crear madre sustituta")
def crear_madre_endpoint(
    datos: MadreCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(_coordinador_o_admin)
) -> MadreOut:
    return crear_madre(session, datos, usuario.id)


@router.get("", response_model=list[MadreOut], summary="Listar madres sustitutas")
def listar_madres_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(_coordinador_o_admin)
) -> list[MadreOut]:
    return listar_madres(session, usuario)


@router.get("/{madre_id}", response_model=MadreOut, summary="Obtener madre sustituta")
def obtener_madre_endpoint(
    madre_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(_coordinador_o_admin)
) -> MadreOut:
    return obtener_madre(session, madre_id, usuario)


@router.put("/{madre_id}", response_model=MadreOut, summary="Actualizar madre sustituta")
def actualizar_madre_endpoint(
    madre_id: uuid.UUID,
    datos: MadreUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(_coordinador_o_admin),
) -> MadreOut:
    return actualizar_madre(session, madre_id, datos, usuario.id, usuario)
