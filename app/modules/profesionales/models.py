import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk


class Profesional(UuidPk, Timestamps, Base):
    __tablename__ = "profesionales"

    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), unique=True, nullable=True)
    nombres: Mapped[str] = mapped_column(String(120))
    apellidos: Mapped[str] = mapped_column(String(120))
    cargo: Mapped[str] = mapped_column(String(40))  # defensor, psicosocial, nutricion, trabajo_social
    especialidad: Mapped[str | None] = mapped_column(String(120), nullable=True)
    numero_registro: Mapped[str | None] = mapped_column(String(60), nullable=True)


class MenorProfesional(UuidPk, Base):
    """Quién atiende a cada menor y en qué rol: de aquí salen permisos y destinatarios de alertas."""

    __tablename__ = "menores_profesionales"
    __table_args__ = (UniqueConstraint("menor_id", "profesional_id", "rol_asignado"),)

    menor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menores.id"), index=True)
    profesional_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("profesionales.id"), index=True)
    rol_asignado: Mapped[str] = mapped_column(String(40))
