"""Asignaciones y Traslados: Esquemas de entrada y salida de la API.

Vincula al menor con el hogar con fecha de inicio y fin; actas de traslado.
"""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .domain import TipoMovimiento


class AsignacionCreate(BaseModel):
    menor_id: uuid.UUID
    hogar_id: uuid.UUID
    fecha_inicio: date
    tipo_movimiento: TipoMovimiento = TipoMovimiento.INGRESO
    acta_referencia: str | None = Field(default=None, max_length=255)
    motivo: str | None = Field(default=None, max_length=255)


class AsignacionCerrar(BaseModel):
    fecha_fin: date | None = None
    motivo: str | None = Field(default=None, max_length=255)
    acta_referencia: str | None = Field(default=None, max_length=255)


class AsignacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    menor_id: uuid.UUID
    hogar_id: uuid.UUID
    fecha_inicio: date
    fecha_fin: date | None = None
    estado: str
    version: int
    tipo_movimiento: str
    acta_referencia: str | None = None
    motivo: str | None = None
    registrado_por: uuid.UUID | None = None


class AsignacionHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asignacion_id: uuid.UUID
    version: int
    menor_id: uuid.UUID
    hogar_id: uuid.UUID
    fecha_inicio: date
    fecha_fin: date | None = None
    estado: str
    tipo_movimiento: str
    acta_referencia: str | None = None
    motivo: str | None = None
    cambiado_por: uuid.UUID | None = None
    created_at: datetime
