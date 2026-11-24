"""Inventario del Hogar: Esquemas de entrada y salida de la API.

Camas, muebles, personas que viven y red de apoyo.
"""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


# ---------------------------------------------------------------------------
# Items (camas, muebles, otro)
# ---------------------------------------------------------------------------

class InventarioItemCreate(BaseModel):
    hogar_id: uuid.UUID
    tipo: str = Field(pattern="^(cama|mueble|otro)$")
    descripcion: str = Field(min_length=1, max_length=255)
    cantidad: int = Field(default=1, ge=1)
    estado: str = Field(default="bueno", pattern="^(bueno|regular|malo|retirado)$")


class InventarioItemUpdate(BaseModel):
    tipo: str | None = Field(default=None, pattern="^(cama|mueble|otro)$")
    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    cantidad: int | None = Field(default=None, ge=1)
    estado: str | None = Field(default=None, pattern="^(bueno|regular|malo|retirado)$")


class InventarioItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hogar_id: uuid.UUID
    tipo: str
    descripcion: str
    cantidad: int
    estado: str
    recibido: bool
    registrado_por: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Recepción y fotos de evidencia (ADR-0014)
# ---------------------------------------------------------------------------

class InventarioRecepcionConfirmar(BaseModel):
    estado: str = Field(pattern="^(bueno|regular|malo)$")


class InventarioItemFotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    mime_type: str
    tamanio_bytes: int
    subido_por: uuid.UUID
    creado_en: datetime
    declaracion_sin_menores: bool
    oculta: bool


# ---------------------------------------------------------------------------
# Convivientes
# ---------------------------------------------------------------------------

class ConvivienteCreate(BaseModel):
    hogar_id: uuid.UUID
    nombres: str = Field(min_length=1, max_length=120)
    relacion_con_madre: str = Field(min_length=1, max_length=60)
    fecha_desde: date | None = None
    observaciones: str | None = Field(default=None, max_length=255)


class ConvivienteUpdate(BaseModel):
    nombres: str | None = Field(default=None, min_length=1, max_length=120)
    relacion_con_madre: str | None = Field(default=None, min_length=1, max_length=60)
    fecha_desde: date | None = None
    observaciones: str | None = Field(default=None, max_length=255)
    activo: bool | None = None


class ConvivienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hogar_id: uuid.UUID
    nombres: str
    relacion_con_madre: str
    fecha_desde: date | None = None
    observaciones: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Red de apoyo
# ---------------------------------------------------------------------------

class RedApoyoCreate(BaseModel):
    hogar_id: uuid.UUID
    nombres: str = Field(min_length=1, max_length=120)
    relacion: str = Field(min_length=1, max_length=60)
    telefono: str | None = Field(default=None, max_length=30)
    observaciones: str | None = Field(default=None, max_length=255)


class RedApoyoUpdate(BaseModel):
    nombres: str | None = Field(default=None, min_length=1, max_length=120)
    relacion: str | None = Field(default=None, min_length=1, max_length=60)
    telefono: str | None = Field(default=None, max_length=30)
    observaciones: str | None = Field(default=None, max_length=255)
    activo: bool | None = None


class RedApoyoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hogar_id: uuid.UUID
    nombres: str
    relacion: str
    telefono: str | None = None
    observaciones: str | None = None
    activo: bool
    created_at: datetime
    updated_at: datetime
    # ADR-0019, sección 5: `foto_ref` nunca se expone (ruta de archivo cifrado interna); solo se
    # informa si hay foto cargada. El contenido se consulta en `GET /inventario/red-apoyo/{id}/foto`.
    foto_ref: str | None = Field(default=None, exclude=True, repr=False)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tiene_foto(self) -> bool:
        return bool(self.foto_ref)
