"""Configuración administrable: esquemas de entrada y salida de la API (ADR-0013, sección 3)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GrupoCatalogoOut(BaseModel):
    grupo: str
    etiqueta: str
    descripcion: str
    con_seccion_acceso: bool
    total_opciones_activas: int


class CatalogoOpcionOut(BaseModel):
    """Lectura pública (cualquier autenticado): solo lo que necesita un formulario."""

    model_config = ConfigDict(from_attributes=True)

    valor: str
    etiqueta: str
    orden: int


class CatalogoOpcionAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    grupo: str
    valor: str
    etiqueta: str
    orden: int
    activo: bool
    seccion_acceso: str | None = None
    creado_en: datetime
    actualizado_en: datetime | None = None
    actualizado_por: uuid.UUID | None = None


class CatalogoOpcionCreate(BaseModel):
    valor: str = Field(min_length=1, max_length=100)
    etiqueta: str = Field(min_length=1, max_length=200)
    orden: int = 0
    # Obligatorio (puede ser explícitamente None = básica) cuando el grupo tiene
    # `con_seccion_acceso=True` (ADR-0013, sección 5.1). Se valida en `application.py`.
    seccion_acceso: str | None = None


class CatalogoOpcionUpdate(BaseModel):
    etiqueta: str | None = Field(default=None, min_length=1, max_length=200)
    orden: int | None = None
    activo: bool | None = None


class ParametroOut(BaseModel):
    clave: str
    etiqueta: str
    descripcion: str
    tipo: str
    grupo: str | None = None
    publico: bool
    valor_actual: str
    valor_por_defecto: str
    editado_por_admin: bool


class ParametroUpdate(BaseModel):
    valor: str = Field(min_length=0, max_length=2000)


class ParametroPublicoOut(BaseModel):
    clave: str
    valor: str
