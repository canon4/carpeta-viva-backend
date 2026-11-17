import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk


class Usuario(UuidPk, Timestamps, Base):
    __tablename__ = "usuarios"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(30))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    zona_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("zonas.id"), nullable=True)
    # Bloqueo por intentos fallidos (migración 0011).
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Tokens emitidos antes de este momento dejan de valer (cambio de contraseña).
    credenciales_cambiadas_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
