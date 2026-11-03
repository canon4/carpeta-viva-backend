import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk


class Asignacion(UuidPk, Timestamps, Base):
    __tablename__ = "asignaciones"
    __table_args__ = (
        CheckConstraint(
            "tipo_movimiento IN ('ingreso', 'traslado', 'egreso')", name="ck_asignaciones_tipo_movimiento"
        ),
    )

    menor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menores.id"), index=True)
    hogar_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("hogares_sustitutos.id"), index=True)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default="vigente")
    version: Mapped[int] = mapped_column(Integer, default=1)
    tipo_movimiento: Mapped[str] = mapped_column(String(20), default="ingreso")
    acta_referencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registrado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=True)


class AsignacionHistory(UuidPk, Base):
    """Snapshot de la fila anterior de `asignaciones`: cierre, traslado, corrección de fechas."""

    __tablename__ = "asignaciones_history"

    asignacion_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("asignaciones.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    menor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menores.id"), index=True)
    hogar_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("hogares_sustitutos.id"))
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    estado: Mapped[str] = mapped_column(String(30))
    tipo_movimiento: Mapped[str] = mapped_column(String(20))
    acta_referencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cambiado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
