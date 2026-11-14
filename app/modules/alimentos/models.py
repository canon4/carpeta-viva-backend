"""Control de Alimentos: Modelos ORM.

Ingreso de cada mercado, si es perecedero y su fecha de vencimiento. Sin borrado físico
(ADR-0009, sección 4): se marca `consumido`.

ADR-0014, sección 4: `AlimentoChecklistItem` es el "producto del mercado" reutilizable; cada
compra sigue siendo un `AlimentoItem` independiente (historial completo), que puede apuntar
opcionalmente al producto del checklist del que viene.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk


class AlimentoChecklistItem(UuidPk, Base):
    __tablename__ = "alimentos_checklist_items"

    hogar_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("hogares_sustitutos.id"), index=True)
    descripcion: Mapped[str] = mapped_column(String(255))
    perecedero: Mapped[bool] = mapped_column(Boolean, default=True)
    unidad_por_defecto: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_por: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
    checklist_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("alimentos_checklist_items.id"), nullable=True
    )
