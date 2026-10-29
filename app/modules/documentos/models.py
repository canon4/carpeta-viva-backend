import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk


class Documento(UuidPk, Timestamps, Base):
    __tablename__ = "documentos"

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


class Reporte(UuidPk, Timestamps, Base):
    __tablename__ = "reportes"

    menor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menores.id"), index=True)
    autor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    tipo_autor: Mapped[str] = mapped_column(String(30))
    tipo_reporte: Mapped[str] = mapped_column(String(60))
    contenido: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=dict)
    referencia_archivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
