"""Asistente de IA: Esquemas de entrada y salida de la API.

Busca, resume y clasifica con citas; consulta solo por la capa de aplicación.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

MENSAJE_ACCESO_REVOCADO = "[contenido ya no accesible: el permiso sobre este expediente fue revocado]"
MENSAJE_SIN_RESULTADO = "No encontré información en los documentos/reportes a los que tiene acceso."
# Regla del chat: sin un menor (o un hogar) elegido, no se busca a ciegas entre todos los
# expedientes a los que el usuario tiene acceso (mezclaría datos de varios NNA en una sola
# respuesta). Se pide identificar al menor antes de buscar, en vez de responder.
MENSAJE_PIDE_IDENTIFICACION = (
    "Para buscar en los expedientes necesito saber de qué niño, niña o adolescente se trata. "
    "Indíqueme su nombre completo o número de identificación, o elíjalo en el selector "
    '"Sobre" antes de preguntar.'
)


class CitaOut(BaseModel):
    documento_id: uuid.UUID | None = None
    reporte_id: uuid.UUID | None = None
    version: int
    categoria: str
    fecha: str
    texto: str = Field(description="Formato de cita ya armado, sin nombres reales (sección 1.5 paso 6)")
    titulo: str = Field(default="", description="Título del documento, o un rótulo genérico para el reporte")


class ConsultaCreate(BaseModel):
    pregunta: str = Field(min_length=1, max_length=2000)
    menor_id: uuid.UUID | None = None
    hogar_id: uuid.UUID | None = None


class ConsultaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    pregunta: str
    respuesta: str
    menor_id: uuid.UUID | None = None
    hogar_id: uuid.UUID | None = None
    fragmentos_usados: list[dict] = Field(default_factory=list)
    modelo: str
    proveedor: str
    anonimizado: bool
    sin_resultado: bool
    duracion_ms: int | None = None
    creado_en: datetime


class ConsultaMetadatosOut(BaseModel):
    """Lo único que ve `auditor` (ADR-0010, sección 1.4/1.9): nunca `pregunta`/`respuesta`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    menor_id: uuid.UUID | None = None
    hogar_id: uuid.UUID | None = None
    fragmentos_usados: list[dict] = Field(default_factory=list)
    modelo: str
    proveedor: str
    anonimizado: bool
    sin_resultado: bool
    duracion_ms: int | None = None
    creado_en: datetime


class ResumenMenorOut(BaseModel):
    menor_id: uuid.UUID
    resumen: str
    citas: list[CitaOut]
    sin_resultado: bool


class ResumenDocumentoOut(BaseModel):
    documento_id: uuid.UUID
    resumen: str
    citas: list[CitaOut]
    sin_resultado: bool


class RedaccionApoyoCreate(BaseModel):
    menor_id: uuid.UUID
    tipo_informe: str = Field(min_length=1, max_length=60)
    notas_profesional: str = Field(min_length=1, max_length=4000)


class RedaccionApoyoOut(BaseModel):
    borrador: str
    citas: list[CitaOut]
    sin_resultado: bool


class EstadoIaOut(BaseModel):
    proveedor_llm: str
    modelo_llm: str
    embeddings_modelo: str
    anonimizado_por_defecto: bool
    seudonimizacion_cobertura: str
    indexar_automaticamente: bool


class IaConfiguracionOut(BaseModel):
    """Nunca incluye la clave: solo si existe, de dónde viene y sus últimos caracteres."""

    proveedor: str
    modelo: str
    clave_origen: str  # "panel" | "entorno" | "ninguna"
    clave_sufijo: str | None = None
    actualizado_en: datetime | None = None
    proveedores_disponibles: list[str]


class IaConfiguracionUpdate(BaseModel):
    proveedor: str | None = Field(default=None, max_length=50)
    modelo: str | None = Field(default=None, min_length=1, max_length=100)
    # Solo escritura. Vacío ("") borra la clave del panel y vuelve a la del entorno.
    api_key: str | None = Field(default=None, max_length=300)


class IaModelosOut(BaseModel):
    proveedor: str
    modelos: list[str]
    error: str | None = None


class IaPruebaOut(BaseModel):
    ok: bool
    mensaje: str


class ReindexarPendientesOut(BaseModel):
    documentos_reindexados: int
    reportes_reindexados: int
    documentos_con_error: list[uuid.UUID]
    reportes_con_error: list[uuid.UUID]
