"""Profesionales: Esquemas de entrada y salida de la API.

Datos del personal profesional (defensor, psicosocial, nutrición, trabajo social).
"""
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ProfesionalCreate(BaseModel):
    usuario_id: uuid.UUID | None = None
    nombres: str = Field(min_length=1, max_length=120)
    apellidos: str = Field(min_length=1, max_length=120)
    cargo: str = Field(min_length=1, max_length=40)
    especialidad: str | None = Field(default=None, max_length=120)
    numero_registro: str | None = Field(default=None, max_length=60)
    telefono: str | None = Field(default=None, max_length=30)


class ProfesionalUpdate(BaseModel):
    nombres: str | None = Field(default=None, min_length=1, max_length=120)
    apellidos: str | None = Field(default=None, min_length=1, max_length=120)
    cargo: str | None = Field(default=None, min_length=1, max_length=40)
    especialidad: str | None = Field(default=None, max_length=120)
    numero_registro: str | None = Field(default=None, max_length=60)
    telefono: str | None = Field(default=None, max_length=30)


class ProfesionalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID | None = None
    nombres: str
    apellidos: str
    cargo: str
    especialidad: str | None = None
    numero_registro: str | None = None
    telefono: str | None = None
