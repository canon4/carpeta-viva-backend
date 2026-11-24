import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import requiere_roles
from app.modules.auth.domain import Rol
from app.modules.auth.models import Usuario

from .application import (
    actualizar_mi_perfil,
    actualizar_profesional,
    crear_profesional,
    listar_profesionales,
    obtener_mi_perfil,
    obtener_profesional,
)
from .schemas import ProfesionalAutoUpdate, ProfesionalCreate, ProfesionalOut, ProfesionalUpdate

router = APIRouter(prefix="/profesionales", tags=["Profesionales"])

_coordinador_o_admin = requiere_roles(Rol.COORDINADOR, Rol.ADMIN)
_profesional_o_defensor = requiere_roles(Rol.PROFESIONAL, Rol.DEFENSOR)


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "profesionales", "estado": "activo"}


@router.get("/yo", response_model=ProfesionalOut, summary="Perfil del profesional/defensor autenticado")
def mi_perfil(
    session: Session = Depends(get_session), usuario: Usuario = Depends(_profesional_o_defensor)
) -> ProfesionalOut:
    return obtener_mi_perfil(session, usuario.id)


@router.put("/yo", response_model=ProfesionalOut, summary="Actualizar mis datos de contacto (teléfono, especialidad)")
def actualizar_mi_perfil_endpoint(
    datos: ProfesionalAutoUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(_profesional_o_defensor),
) -> ProfesionalOut:
    return actualizar_mi_perfil(session, usuario.id, datos)


@router.post("", response_model=ProfesionalOut, status_code=status.HTTP_201_CREATED, summary="Crear profesional")
def crear_profesional_endpoint(
    datos: ProfesionalCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(_coordinador_o_admin)
) -> ProfesionalOut:
    return crear_profesional(session, datos, usuario.id)


@router.get("", response_model=list[ProfesionalOut], summary="Listar profesionales")
def listar_profesionales_endpoint(
    cargo: str | None = None,
    session: Session = Depends(get_session),
    _=Depends(_coordinador_o_admin),
) -> list[ProfesionalOut]:
    return listar_profesionales(session, cargo)


@router.get("/{profesional_id}", response_model=ProfesionalOut, summary="Obtener profesional")
def obtener_profesional_endpoint(
    profesional_id: uuid.UUID, session: Session = Depends(get_session), _=Depends(_coordinador_o_admin)
) -> ProfesionalOut:
    return obtener_profesional(session, profesional_id)


@router.put("/{profesional_id}", response_model=ProfesionalOut, summary="Actualizar profesional")
def actualizar_profesional_endpoint(
    profesional_id: uuid.UUID,
    datos: ProfesionalUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(_coordinador_o_admin),
) -> ProfesionalOut:
    return actualizar_profesional(session, profesional_id, datos, usuario.id)
