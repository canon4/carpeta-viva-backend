"""Zonas y Hogares: Esquemas de entrada y salida de la API.

Organiza los hogares sustitutos por zona y guarda los datos de cada hogar.
"""
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from .domain import CAPACIDAD_MAXIMA_NORMATIVA, EstadoHogar


class ZonaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=255)


class ZonaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion: str | None = Field(default=None, max_length=255)


class ZonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    descripcion: str | None = None


class HogarCreate(BaseModel):
    zona_id: uuid.UUID
    capacidad_maxima: int = Field(default=6, ge=1, le=CAPACIDAD_MAXIMA_NORMATIVA)
    fecha_habilitacion: date | None = None


class HogarUpdate(BaseModel):
    madre_id: uuid.UUID | None = None
    capacidad_maxima: int | None = Field(default=None, ge=1, le=CAPACIDAD_MAXIMA_NORMATIVA)
    estado: EstadoHogar | None = None


class HogarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    zona_id: uuid.UUID
    madre_id: uuid.UUID | None = None
    capacidad_maxima: int
    fecha_habilitacion: date | None = None
    estado: str
