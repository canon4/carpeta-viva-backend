"""Alertas y Evasiones: esquemas de entrada y salida de la API (ADR-0009, sección 1)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvasionCreate(BaseModel):
    menor_id: uuid.UUID
    descripcion: str = Field(min_length=1, max_length=255)


class AlertaDestinatarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    visto_en: datetime | None = None
    # `notificado_en` deliberadamente NO se expone (ADR-0009, revisión de seguridad punto 6):
    # siempre NULL en esta fase, no hay integración SMS/push; exponerlo insinuaría un canal de
    # aviso que no existe.


class AlertaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: str
    menor_id: uuid.UUID
    origen: str
    generada_por: uuid.UUID | None = None
    descripcion: str
    detalle: dict | None = None
    estado: str
    created_at: datetime
    destinatarios: list[AlertaDestinatarioOut] = Field(default_factory=list)


class ContactoEmergencia(BaseModel):
    """Teléfono del profesional realmente asignado; si no está registrado se dice explícitamente
    (ADR-0009, sección 1) en vez de omitir el campo en silencio."""

    rol_asignado: str
    nombres: str | None = None
    telefono: str | None = None
    nota: str | None = None


class ContactosEmergenciaOut(BaseModel):
    policia_infancia_telefono: str
    contactos: list[ContactoEmergencia] = Field(default_factory=list)


class EvasionReportadaOut(BaseModel):
    alerta: AlertaOut
    contactos_emergencia: ContactosEmergenciaOut
