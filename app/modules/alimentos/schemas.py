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
    checklist_item_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Checklist reutilizable (ADR-0014, sección 4)
# ---------------------------------------------------------------------------

class AlimentoChecklistItemCreate(BaseModel):
    hogar_id: uuid.UUID
    descripcion: str = Field(min_length=1, max_length=255)
    perecedero: bool = True
    unidad_por_defecto: str | None = Field(default=None, max_length=20)


class AlimentoChecklistItemUpdate(BaseModel):
    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    unidad_por_defecto: str | None = Field(default=None, max_length=20)
    activo: bool | None = None


class AlimentoChecklistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hogar_id: uuid.UUID
    descripcion: str
    perecedero: bool
    unidad_por_defecto: str | None = None
    activo: bool
    creado_por: uuid.UUID
    creado_en: datetime


class AlimentoChecklistComprar(BaseModel):
    fecha_ingreso: date
    fecha_vencimiento: date | None = None
    cantidad: float = Field(gt=0)
    unidad: str | None = Field(default=None, max_length=20)
