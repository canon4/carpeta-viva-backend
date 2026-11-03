"""Inventario del Hogar: Modelos ORM.

Camas, muebles, personas que viven en el hogar y red de apoyo. Sin borrado físico (ADR-0009,
sección 3): `InventarioItem` se marca `retirado`, `HogarConviviente`/`HogarRedApoyo` se marcan
`activo=false`.
"""
import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk

TIPOS_INVENTARIO = ("cama", "mueble", "otro")
ESTADOS_INVENTARIO = ("bueno", "regular", "malo", "retirado")


class InventarioItem(UuidPk, Timestamps, Base):
    __tablename__ = "inventario_items"
    __table_args__ = (
        CheckConstraint("tipo IN (" + ", ".join(f"'{t}'" for t in TIPOS_INVENTARIO) + ")", name="ck_inventario_items_tipo"),
        CheckConstraint(
            "estado IN (" + ", ".join(f"'{e}'" for e in ESTADOS_INVENTARIO) + ")", name="ck_inventario_items_estado"
        ),
    )

    hogar_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("hogares_sustitutos.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    descripcion: Mapped[str] = mapped_column(String(255))
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    estado: Mapped[str] = mapped_column(String(20), default="bueno")
    registrado_por: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"))


class HogarConviviente(UuidPk, Timestamps, Base):
    """Personas que viven en el hogar, distintas de los NNA asignados y la madre."""

    __tablename__ = "hogar_convivientes"

    hogar_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("hogares_sustitutos.id"), index=True)
    nombres: Mapped[str] = mapped_column(String(120))
    relacion_con_madre: Mapped[str] = mapped_column(String(60))
    fecha_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    observaciones: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class HogarRedApoyo(UuidPk, Timestamps, Base):
    __tablename__ = "hogar_red_apoyo"

    hogar_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("hogares_sustitutos.id"), index=True)
    nombres: Mapped[str] = mapped_column(String(120))
    relacion: Mapped[str] = mapped_column(String(60))
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
