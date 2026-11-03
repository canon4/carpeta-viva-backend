"""Auditoría: Casos de uso.

Registro de solo inserción de todo acceso a datos; sin edición ni borrado.
"""
from sqlalchemy.orm import Session

from .domain import FiltroAuditoria
from .models import AuditoriaAcceso
from .repository import AuditoriaRepository


def listar_accesos(session: Session, filtro: FiltroAuditoria) -> list[AuditoriaAcceso]:
    return AuditoriaRepository(session).listar(filtro)
