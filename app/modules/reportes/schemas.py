"""Reportes: Esquemas de entrada y salida de la API (ADR-0010, sección 2)."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ReporteAgregadoOut(BaseModel):
    """`GET /reportes/general` y `GET /reportes/zona/{zona_id}`: mismos campos, `zona_id` es
    `None` solo cuando `general` lo ve `admin`/`auditor` sin acotar (todas las zonas)."""

    zona_id: uuid.UUID | None = None
    menores_por_estado: dict[str, int]
    hogares_total: int
    hogares_capacidad_total: int
    hogares_con_ocupacion_vigente: int
    documentos_pendientes_revision: int
    alertas_activas_por_tipo: dict[str, int]
    citas_vencidas: int
    alimentos_vencidos: int


class DocumentoResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    categoria: str
    titulo: str
    estado_flujo: str


class ReporteMenorOut(BaseModel):
    menor_id: uuid.UUID
    estado_actual: str
    asignacion_vigente_hogar_id: uuid.UUID | None = None
    documentos_por_categoria: dict[str, int]
    documentos_visibles: list[DocumentoResumen]
    reportes_por_tipo: dict[str, int]
    alertas_activas: int
    citas_proximas: int
    secciones_sin_acceso: list[str] = Field(default_factory=list)


class ReporteMadreOut(BaseModel):
    madre_id: uuid.UUID
    hogares: list[uuid.UUID]
    menores_asignados: list[uuid.UUID]
    documentos_creados_por_ella_por_estado: dict[str, int]
    alertas_activas: int
    inventario_items: int
    alimentos_vencidos: int
    solo_agregado: bool = False


class ExportarRequest(BaseModel):
    nivel: str
    zona_id: uuid.UUID | None = None
    menor_id: uuid.UUID | None = None
    madre_id: uuid.UUID | None = None
    formato: str = "json"


class InformeGeneradoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    nivel: str
    filtros: dict
    formato: str
    referencia_archivo: str | None = None
    generado_en: datetime
