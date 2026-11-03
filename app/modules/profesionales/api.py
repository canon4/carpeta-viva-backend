import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import requiere_roles
from app.modules.auth.domain import Rol
from app.modules.auth.models import Usuario

from .application import actualizar_profesional, crear_profesional, listar_profesionales, obtener_profesional
from .schemas import ProfesionalCreate, ProfesionalOut, ProfesionalUpdate

router = APIRouter(prefix="/profesionales", tags=["Profesionales"])

_coordinador_o_admin = requiere_roles(Rol.COORDINADOR, Rol.ADMIN)


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "profesionales", "estado": "activo"}


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
