"""Gestión Documental: Esquemas de entrada y salida de la API.

Carga, clasificación, versionado y flujo de revisión: la madre crea, el profesional aprueba.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    menor_id: uuid.UUID | None = None
    hogar_id: uuid.UUID | None = None
    categoria: str
    titulo: str
    estado_flujo: str
    version: int
    hash_sha256: str | None = None
    sensible: bool
    creado_por: uuid.UUID
    nombre_original: str
    mime_type: str
    tamanio_bytes: int
    revisado_por: uuid.UUID | None = None
    revisado_en: datetime | None = None
    motivo_devolucion: str | None = None
    created_at: datetime
    # ADR-0018: subida propia de la madre en una sección que no puede leer; solo metadatos.
    reservado: bool = False


class DocumentoVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    documento_id: uuid.UUID
    version: int
    hash_sha256: str | None = None
    nombre_original: str | None = None
    mime_type: str | None = None
    tamanio_bytes: int | None = None
    estado_flujo: str
    creado_por: uuid.UUID | None = None
    revisado_por: uuid.UUID | None = None
    motivo_devolucion: str | None = None
    comprimida: bool = False
    created_at: datetime


class DocumentoDevolver(BaseModel):
    motivo: str = Field(min_length=1, max_length=255)


class ReporteCreate(BaseModel):
    menor_id: uuid.UUID
    tipo_reporte: str = Field(min_length=1, max_length=60)
    contenido: dict = Field(default_factory=dict)
    referencia_archivo: str | None = Field(default=None, max_length=255)


class ReporteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    menor_id: uuid.UUID
    autor_id: uuid.UUID
    tipo_autor: str
    tipo_reporte: str
    contenido: dict
    referencia_archivo: str | None = None
    version: int
    created_at: datetime


class SeccionExpedienteOut(BaseModel):
    """Agregador de `Documento` + `Reporte` de una sección (salud/psicosocial/familia)."""

    menor_id: uuid.UUID
    seccion: str
    documentos: list[DocumentoOut]
    reportes: list[ReporteOut]
