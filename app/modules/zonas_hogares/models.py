import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk


class Zona(UuidPk, Timestamps, Base):
    __tablename__ = "zonas"

    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)


class HogarSustituto(UuidPk, Timestamps, Base):
    __tablename__ = "hogares_sustitutos"

    zona_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("zonas.id"), index=True)
    madre_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("madres_sustitutas.id"), nullable=True)
    capacidad_maxima: Mapped[int] = mapped_column(Integer, default=6)
    fecha_habilitacion: Mapped[date | None] = mapped_column(Date, nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default="activo")
