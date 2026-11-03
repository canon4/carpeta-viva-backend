"""Madres Sustitutas: Esquemas de entrada y salida de la API.

Datos de la madre sustituta: identificación, certificación y firma única.
"""
import uuid

from pydantic import BaseModel, ConfigDict, Field

from .domain import EstadoCertificacion


class MadreCreate(BaseModel):
    usuario_id: uuid.UUID | None = None
    nombres: str = Field(min_length=1, max_length=120)
    apellidos: str = Field(min_length=1, max_length=120)
    numero_identificacion: str = Field(min_length=1, max_length=30)
    direccion: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=30)


class MadreUpdate(BaseModel):
    direccion: str | None = Field(default=None, max_length=255)
    telefono: str | None = Field(default=None, max_length=30)
    estado_certificacion: EstadoCertificacion | None = None


class MadreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID | None = None
    nombres: str
    apellidos: str
    numero_identificacion: str
    direccion: str | None = None
    telefono: str | None = None
    estado_certificacion: str
    firma_ref: str | None = None


class FirmaUpdate(BaseModel):
    firma_ref: str = Field(min_length=1, max_length=255)
