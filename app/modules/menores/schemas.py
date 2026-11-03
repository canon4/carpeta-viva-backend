"""Menores y Expedientes: Esquemas de entrada y salida de la API.

Carpeta digital de cada menor: datos personales, padres, historial médico y psicosocial, estado.
"""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .domain import EstadoMenor, EstadoVital, Parentesco, SeccionSensible, TipoDocumento


class MenorCreate(BaseModel):
    nombres: str = Field(min_length=1, max_length=120)
    apellidos: str = Field(min_length=1, max_length=120)
    fecha_nacimiento: date
    genero: str | None = Field(default=None, max_length=20)
    tipo_documento: TipoDocumento | None = None
    numero_documento: str | None = Field(default=None, max_length=50)


class MenorUpdate(BaseModel):
    nombres: str | None = Field(default=None, min_length=1, max_length=120)
    apellidos: str | None = Field(default=None, min_length=1, max_length=120)
    fecha_nacimiento: date | None = None
    genero: str | None = Field(default=None, max_length=20)
    tipo_documento: TipoDocumento | None = None
    numero_documento: str | None = Field(default=None, max_length=50)
    estado_actual: EstadoMenor | None = None
    motivo: str | None = Field(default=None, max_length=255)


class MenorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombres: str
    apellidos: str
    fecha_nacimiento: date
    genero: str | None = None
    tipo_documento: str | None = None
    numero_documento: str | None = None
    estado_actual: str
    version: int


class MenorHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    menor_id: uuid.UUID
    version: int
    nombres: str
    apellidos: str
    fecha_nacimiento: date
    genero: str | None = None
    tipo_documento: str | None = None
    numero_documento: str | None = None
    estado_actual: str
    cambiado_por: uuid.UUID | None = None
    motivo: str | None = None
    created_at: datetime


class FamiliarCreate(BaseModel):
    parentesco: Parentesco
    nombres: str | None = Field(default=None, max_length=120)
    numero_identificacion: str | None = Field(default=None, max_length=50)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=255)
    estado_vital: EstadoVital = EstadoVital.DESCONOCIDO
    observaciones: str | None = None


class FamiliarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    menor_id: uuid.UUID
    parentesco: str
    nombres: str | None = None
    numero_identificacion: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    estado_vital: str
    observaciones: str | None = None


class PermisoCreate(BaseModel):
    seccion: SeccionSensible
    usuario_id: uuid.UUID
    notas: str | None = Field(default=None, max_length=255)


class PermisoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    menor_id: uuid.UUID
    seccion: str
    usuario_id: uuid.UUID
    otorgado_por: uuid.UUID
    activo: bool
    notas: str | None = None


class MenorPanelItem(BaseModel):
    menor: MenorOut
    hogar_id: uuid.UUID
    zona_id: uuid.UUID


class HogarPanelGroup(BaseModel):
    hogar_id: uuid.UUID
    menores: list[MenorOut]


class ZonaPanelGroup(BaseModel):
    zona_id: uuid.UUID
    hogares: list[HogarPanelGroup]
