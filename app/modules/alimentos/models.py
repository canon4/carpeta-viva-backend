"""Control de Alimentos: Modelos ORM.

Ingreso de cada mercado, si es perecedero y su fecha de vencimiento. Sin borrado físico
(ADR-0009, sección 4): se marca `consumido`.
"""
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk


class AlimentoItem(UuidPk, Timestamps, Base):
    __tablename__ = "alimentos_items"

    hogar_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("hogares_sustitutos.id"), index=True)
    descripcion: Mapped[str] = mapped_column(String(255))
    fecha_ingreso: Mapped[date] = mapped_column(Date)
    perecedero: Mapped[bool] = mapped_column(Boolean)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    cantidad: Mapped[float] = mapped_column(Float)
    unidad: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consumido: Mapped[bool] = mapped_column(Boolean, default=False)
    registrado_por: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"))
