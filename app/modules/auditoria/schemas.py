"""Auditoría: Esquemas de entrada y salida de la API.

Registro de solo inserción de todo acceso a datos; sin edición ni borrado.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditoriaAccesoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID | None = None
    accion: str
    recurso: str | None = None
    menor_id: uuid.UUID | None = None
    ip: str | None = None
    created_at: datetime
