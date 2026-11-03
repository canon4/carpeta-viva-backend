"""Auditoría: Entidades, objetos de valor y reglas de negocio.

Registro de solo inserción de todo acceso a datos; sin edición ni borrado.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class FiltroAuditoria:
    usuario_id: UUID | None = None
    accion: str | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
    limit: int = 50
    offset: int = 0
