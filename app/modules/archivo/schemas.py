"""Archivo y Cierre: Esquemas de entrada y salida de la API."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CerrarExpedienteRequest(BaseModel):
    motivo: str = Field(min_length=1, max_length=255)


class ExpedienteArchivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    menor_id: uuid.UUID
    estado: str
    archivado_en: datetime | None = None
    archivado_por: uuid.UUID | None = None
    motivo: str | None = None
    zona_id: uuid.UUID | None = None
    paquete_hash: str | None = None
    destino: str
    enviado_en: datetime | None = None


class ExpedienteArchivoListadoParams(BaseModel):
    zona_id: uuid.UUID | None = None
    desde: date | None = None
    hasta: date | None = None
