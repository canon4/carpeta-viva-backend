import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UuidPk


class AuditoriaAcceso(UuidPk, Base):
    """Tabla de solo inserción. Particionar por fecha cuando crezca (ver ADR-0004)."""

    __tablename__ = "auditoria_accesos"

    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), index=True, nullable=True)
    accion: Mapped[str] = mapped_column(String(60), index=True)
    recurso: Mapped[str | None] = mapped_column(String(255), nullable=True)
    menor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
