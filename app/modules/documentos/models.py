import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk

ESTADOS_FLUJO = ("borrador", "en_revision", "aprobado", "devuelto")


class Documento(UuidPk, Timestamps, Base):
    __tablename__ = "documentos"
    __table_args__ = (
        # Sin CheckConstraint para `categoria` desde ADR-0013: el conjunto de valores válidos ya
        # no es fijo en código (`admin` agrega categorías nuevas en `catalogos_opciones` sin
        # redespliegue); la validación vive en `documentos.application.crear_documento` contra
        # `configuracion.application.valor_valido_en_catalogo`.
        CheckConstraint(
            "estado_flujo IN (" + ", ".join(f"'{e}'" for e in ESTADOS_FLUJO) + ")", name="ck_documentos_estado_flujo"
        ),
        Index("ix_documentos_menor_id_categoria", "menor_id", "categoria"),
    )

    menor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("menores.id"), index=True, nullable=True)
    hogar_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("hogares_sustitutos.id"), index=True, nullable=True)
    categoria: Mapped[str] = mapped_column(String(60))
    titulo: Mapped[str] = mapped_column(String(255))
    estado_flujo: Mapped[str] = mapped_column(String(30), default="borrador")
    version: Mapped[int] = mapped_column(Integer, default=1)
    referencia_archivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hash_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sensible: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_por: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    nombre_original: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    tamanio_bytes: Mapped[int] = mapped_column(Integer)
    revisado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=True)
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motivo_devolucion: Mapped[str | None] = mapped_column(String(255), nullable=True)


class DocumentoVersion(UuidPk, Base):
    """Snapshot de una versión reemplazada de `Documento` (ADR-0008, sección 3/5), patrón `*_History`."""

    __tablename__ = "documentos_versiones"

    documento_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documentos.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    referencia_archivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hash_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nombre_original: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tamanio_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estado_flujo: Mapped[str] = mapped_column(String(30))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=True)
    revisado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=True)
    motivo_devolucion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comprimida: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Reporte(UuidPk, Timestamps, Base):
    __tablename__ = "reportes"

    menor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menores.id"), index=True)
    autor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    tipo_autor: Mapped[str] = mapped_column(String(30))
    tipo_reporte: Mapped[str] = mapped_column(String(60))
    contenido: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=dict)
    referencia_archivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
