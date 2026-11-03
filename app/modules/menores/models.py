import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk


class Menor(UuidPk, Timestamps, Base):
    __tablename__ = "menores"
    __table_args__ = (
        CheckConstraint(
            "tipo_documento IS NULL OR tipo_documento IN "
            "('registro_civil', 'tarjeta_identidad', 'cedula', 'pasaporte', 'sin_documento')",
            name="ck_menores_tipo_documento",
        ),
        CheckConstraint(
            "estado_actual IN ('activo', 'egresado', 'evadido', 'fallecido')",
            name="ck_menores_estado_actual",
        ),
        Index(
            "ix_menores_numero_documento",
            "numero_documento",
            unique=True,
            postgresql_where=text("numero_documento IS NOT NULL"),
        ),
    )

    nombres: Mapped[str] = mapped_column(String(120))
    apellidos: Mapped[str] = mapped_column(String(120))
    fecha_nacimiento: Mapped[date] = mapped_column(Date)
    genero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tipo_documento: Mapped[str | None] = mapped_column(String(30), nullable=True)
    numero_documento: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estado_actual: Mapped[str] = mapped_column(String(30), default="activo")
    version: Mapped[int] = mapped_column(Integer, default=1)


class MenorHistory(UuidPk, Base):
    """Snapshot de la fila anterior de `menores` cada vez que cambian datos personales o estado."""

    __tablename__ = "menores_history"

    menor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menores.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    nombres: Mapped[str] = mapped_column(String(120))
    apellidos: Mapped[str] = mapped_column(String(120))
    fecha_nacimiento: Mapped[date] = mapped_column(Date)
    genero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tipo_documento: Mapped[str | None] = mapped_column(String(30), nullable=True)
    numero_documento: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estado_actual: Mapped[str] = mapped_column(String(30))
    cambiado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MenorFamiliar(UuidPk, Timestamps, Base):
    """Información de padre, madre u otro familiar relevante. Sección siempre sensible ("familia")."""

    __tablename__ = "menores_familiares"
    __table_args__ = (
        CheckConstraint("parentesco IN ('padre', 'madre', 'otro')", name="ck_menores_familiares_parentesco"),
        CheckConstraint(
            "estado_vital IN ('vivo', 'fallecido', 'desconocido')", name="ck_menores_familiares_estado_vital"
        ),
    )

    menor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menores.id"), index=True)
    parentesco: Mapped[str] = mapped_column(String(20))
    nombres: Mapped[str | None] = mapped_column(String(120), nullable=True)
    numero_identificacion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estado_vital: Mapped[str] = mapped_column(String(20))
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)


class PermisoExpediente(UuidPk, Timestamps, Base):
    """ACL: habilita a la madre asignada a ver una sección sensible del expediente."""

    __tablename__ = "permisos_expediente"
    __table_args__ = (
        UniqueConstraint("menor_id", "seccion", "usuario_id", name="uq_permisos_expediente_menor_seccion_usuario"),
        CheckConstraint("seccion IN ('familia', 'salud', 'psicosocial')", name="ck_permisos_expediente_seccion"),
    )

    menor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menores.id"), index=True)
    seccion: Mapped[str] = mapped_column(String(20))
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"), index=True)
    otorgado_por: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    notas: Mapped[str | None] = mapped_column(String(255), nullable=True)
