import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import requiere_roles
from app.modules.auth.domain import Rol

from .application import listar_accesos
from .domain import FiltroAuditoria
from .schemas import AuditoriaAccesoOut

router = APIRouter(prefix="/auditoria", tags=["Auditoría"])

_auditor_o_admin = requiere_roles(Rol.AUDITOR, Rol.ADMIN)


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "auditoria", "estado": "activo"}


@router.get("", response_model=list[AuditoriaAccesoOut], summary="Listar accesos auditados")
def listar_accesos_endpoint(
    usuario_id: uuid.UUID | None = None,
    accion: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _=Depends(_auditor_o_admin),
) -> list[AuditoriaAccesoOut]:
    filtro = FiltroAuditoria(
        usuario_id=usuario_id, accion=accion, desde=desde, hasta=hasta, limit=limit, offset=offset
    )
    return listar_accesos(session, filtro)
