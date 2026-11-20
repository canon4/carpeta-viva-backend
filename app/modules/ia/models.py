"""Asistente de IA: modelos ORM (ADR-0010, sección 1.4, migración 0005).

`FragmentoDocumento` guarda el texto y el embedding de cada fragmento de un `Documento` o
`Reporte` ya indexado para RAG. Los campos `menor_id`/`hogar_id`/`seccion` están denormalizados
para acotar la búsqueda vectorial, pero **no sustituyen la autorización real**: toda lectura
vuelve a pasar por `puede_ver_menor`/`tiene_permiso_seccion` antes de devolver el fragmento
(ADR-0007/ADR-0010 sección 1.4).

`UniqueConstraint(documento_id, version_documento, orden)` (y su equivalente para
`reporte_id`) existe para que reintentar la indexación sea un upsert idempotente, corrección
obligatoria de la revisión de seguridad de ADR-0010 (sección 1.3/1.4): si la tarea en segundo
plano se pierde a medias y se reintenta, no debe duplicar fragmentos de la misma versión.

`IaConsulta` es la auditoría obligatoria de cada respuesta del asistente (ADR-0002 punto 7).
`respuesta` contiene datos reales ya restituidos: es contenido de expediente, no un metadato
(`auditor` no debe leer `pregunta`/`respuesta` en texto completo — regla de la capa de
aplicación, no de este modelo). La revalidación de acceso al leer el propio historial
(sección 1.4, hueco corregido por seguridad) también es responsabilidad de la capa de
aplicación, no de este modelo de datos.
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base, UuidPk

SECCIONES_FRAGMENTO = ("familia", "salud", "psicosocial")
DIMENSION_EMBEDDING = 384


class FragmentoDocumento(UuidPk, Base):
    __tablename__ = "fragmentos_documento"
    __table_args__ = (
        CheckConstraint(
            "(documento_id IS NOT NULL AND reporte_id IS NULL) "
            "OR (documento_id IS NULL AND reporte_id IS NOT NULL)",
            name="ck_fragmentos_documento_documento_xor_reporte",
        ),
        CheckConstraint(
            "seccion IS NULL OR seccion IN (" + ", ".join(f"'{s}'" for s in SECCIONES_FRAGMENTO) + ")",
            name="ck_fragmentos_documento_seccion",
        ),
        UniqueConstraint(
            "documento_id", "version_documento", "orden", name="uq_fragmentos_documento_documento_version_orden"
        ),
        UniqueConstraint(
            "reporte_id", "version_documento", "orden", name="uq_fragmentos_documento_reporte_version_orden"
        ),
        Index(
            "ix_fragmentos_documento_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    documento_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("documentos.id"), index=True, nullable=True)
    reporte_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("reportes.id"), index=True, nullable=True)
    menor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("menores.id"), index=True, nullable=True)
    hogar_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("hogares_sustitutos.id"), index=True, nullable=True)
    seccion: Mapped[str | None] = mapped_column(String(20), nullable=True)
    version_documento: Mapped[int] = mapped_column(Integer)
    orden: Mapped[int] = mapped_column(Integer)
    texto: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSION_EMBEDDING))
    modelo_embedding: Mapped[str] = mapped_column(String(100))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IaConfiguracion(UuidPk, Base):
    """Configuración del proveedor de IA editable por el admin (ADR-0017). Una sola fila.

    La clave de API se guarda cifrada con la clave maestra (`app/core/secretos.py`) y nunca se
    devuelve por la API; `api_key_sufijo` (últimos 4 caracteres) permite reconocerla en pantalla.
    Si no hay fila o no tiene clave, se usa la del entorno (`ANTHROPIC_API_KEY`/`GROQ_API_KEY`).
    """

    __tablename__ = "ia_configuracion"

    proveedor: Mapped[str] = mapped_column(String(50))
    modelo: Mapped[str] = mapped_column(String(100))
    api_key_cifrada: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_sufijo: Mapped[str | None] = mapped_column(String(8), nullable=True)
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IaConsulta(UuidPk, Base):
    __tablename__ = "ia_consultas"

    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"), index=True)
    pregunta: Mapped[str] = mapped_column(Text)
    menor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("menores.id"), index=True, nullable=True)
    hogar_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("hogares_sustitutos.id"), index=True, nullable=True)
    fragmentos_usados: Mapped[list] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=list)
    respuesta: Mapped[str] = mapped_column(Text)
    modelo: Mapped[str] = mapped_column(String(100))
    proveedor: Mapped[str] = mapped_column(String(50))
    anonimizado: Mapped[bool] = mapped_column(Boolean, default=True)
    sin_resultado: Mapped[bool] = mapped_column(Boolean, default=False)
    duracion_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
