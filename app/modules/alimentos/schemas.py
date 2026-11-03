"""Control de Alimentos: Esquemas de entrada y salida de la API.

Ingreso de cada mercado, si es perecedero y su fecha de vencimiento.
"""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AlimentoItemCreate(BaseModel):
    hogar_id: uuid.UUID
    descripcion: str = Field(min_length=1, max_length=255)
    fecha_ingreso: date
    perecedero: bool
    fecha_vencimiento: date | None = None
    cantidad: float = Field(gt=0)
    unidad: str | None = Field(default=None, max_length=20)


class AlimentoItemUpdate(BaseModel):
    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    fecha_ingreso: date | None = None
    perecedero: bool | None = None
    fecha_vencimiento: date | None = None
    cantidad: float | None = Field(default=None, gt=0)
    unidad: str | None = Field(default=None, max_length=20)


class AlimentoItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hogar_id: uuid.UUID
    descripcion: str
    fecha_ingreso: date
    perecedero: bool
    fecha_vencimiento: date | None = None
    cantidad: float
    unidad: str | None = None
    consumido: bool
    registrado_por: uuid.UUID
    created_at: datetime
    updated_at: datetime
