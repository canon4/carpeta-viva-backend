"""Alertas y Evasiones: modelos ORM (ADR-0009, sección 1, migración 0004).

`Alerta` no usa `Timestamps` (solo tiene `created_at`, nunca `updated_at`: no se edita, solo se
cierra con `estado`). `AlertaDestinatario.notificado_en` queda reservado para el aviso adicional
por SMS/push (punto abierto 7/8 de CLAUDE.md): ningún endpoint lo escribe en esta fase.
"""
import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UuidPk

TIPOS_ALERTA = ("evasion", "visita_vencida", "documento_faltante")
ORIGENES_ALERTA = ("manual", "automatica")
ESTADOS_ALERTA = ("activa", "cerrada")


class Alerta(UuidPk, Base):
    __tablename__ = "alertas"
    __table_args__ = (
        CheckConstraint("tipo IN (" + ", ".join(f"'{t}'" for t in TIPOS_ALERTA) + ")", name="ck_alertas_tipo"),
        CheckConstraint("origen IN (" + ", ".join(f"'{o}'" for o in ORIGENES_ALERTA) + ")", name="ck_alertas_origen"),
        CheckConstraint("estado IN (" + ", ".join(f"'{e}'" for e in ESTADOS_ALERTA) + ")", name="ck_alertas_estado"),
    )

    tipo: Mapped[str] = mapped_column(String(30))
    menor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menores.id"), index=True)
    origen: Mapped[str] = mapped_column(String(20))
    generada_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=True)
    descripcion: Mapped[str] = mapped_column(String(255))
    detalle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default="activa")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertaDestinatario(UuidPk, Base):
    __tablename__ = "alertas_destinatarios"
    __table_args__ = (UniqueConstraint("alerta_id", "usuario_id", name="uq_alertas_destinatarios_alerta_usuario"),)

    alerta_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("alertas.id"), index=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"), index=True)
    visto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Reservado para el aviso adicional SMS/push (ADR-0009, revisión de seguridad punto 6): no
    # escrito por ningún endpoint ni proceso en esta fase, siempre NULL.
    notificado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Reservado para aviso adicional SMS/push (no implementado en esta fase; siempre NULL).",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
