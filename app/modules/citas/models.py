"""Citas y Recordatorios: modelo ORM (ADR-0009, sección 2, migración 0004).

Sin tabla `_History`: la trazabilidad de cambios la cubre `auditoria_accesos` (mismo criterio
que ADR-0007 §3 aplicó a `menores_familiares`).
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk

TIPOS_CITA = ("medica", "psicosocial", "reunion_familia", "otro")
ESTADOS_CITA = ("pendiente", "cumplida", "no_asistio")


class Cita(UuidPk, Timestamps, Base):
    __tablename__ = "citas"
    __table_args__ = (
        CheckConstraint("tipo IN (" + ", ".join(f"'{t}'" for t in TIPOS_CITA) + ")", name="ck_citas_tipo"),
        CheckConstraint("estado IN (" + ", ".join(f"'{e}'" for e in ESTADOS_CITA) + ")", name="ck_citas_estado"),
    )

    menor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menores.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lugar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    registrado_por: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"))
