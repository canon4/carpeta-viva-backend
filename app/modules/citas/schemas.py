"""Citas y Recordatorios: esquemas de entrada y salida de la API (ADR-0009, sección 2)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CitaCreate(BaseModel):
    menor_id: uuid.UUID
    tipo: str = Field(min_length=1, max_length=30)
    fecha_hora: datetime
    lugar: str | None = Field(default=None, max_length=255)
    notas: str | None = None


class CitaUpdate(BaseModel):
    fecha_hora: datetime | None = None
    lugar: str | None = Field(default=None, max_length=255)
    notas: str | None = None


class CitaEstadoUpdate(BaseModel):
    estado: str = Field(min_length=1, max_length=20)


class CitaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    menor_id: uuid.UUID
    tipo: str
    fecha_hora: datetime
    lugar: str | None = None
    # `null` cuando el solicitante no tiene `tiene_permiso_seccion` para la sección mapeada del
    # tipo de cita (ADR-0009, corrección de seguridad sección 2): el resto de la fila sí se
    # muestra, es solo agenda.
    notas: str | None = None
    estado: str
    registrado_por: uuid.UUID
    created_at: datetime
    updated_at: datetime
