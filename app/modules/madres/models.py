import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk


class MadreSustituta(UuidPk, Timestamps, Base):
    __tablename__ = "madres_sustitutas"

    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), unique=True, nullable=True)
    nombres: Mapped[str] = mapped_column(String(120))
    apellidos: Mapped[str] = mapped_column(String(120))
    numero_identificacion: Mapped[str] = mapped_column(String(30), unique=True)
    direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    estado_certificacion: Mapped[str] = mapped_column(String(30), default="pendiente")
    firma_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
