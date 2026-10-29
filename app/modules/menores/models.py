from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk


class Menor(UuidPk, Timestamps, Base):
    __tablename__ = "menores"

    nombres: Mapped[str] = mapped_column(String(120))
    apellidos: Mapped[str] = mapped_column(String(120))
    fecha_nacimiento: Mapped[date] = mapped_column(Date)
    genero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estado_actual: Mapped[str] = mapped_column(String(30), default="activo")
    version: Mapped[int] = mapped_column(Integer, default=1)
