"""Configuración administrable: modelos ORM (ADR-0013, sección 1, migración 0009).

Sin borrado físico: una opción de catálogo se desactiva (`activo=False`), nunca se borra.
`configuracion_sistema` es una tabla clave/valor; cada lector castea el texto según el tipo
declarado en `configuracion.domain.REGISTRO_PARAMETROS`.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UuidPk


class CatalogoOpcion(UuidPk, Base):
    __tablename__ = "catalogos_opciones"
    __table_args__ = (UniqueConstraint("grupo", "valor", name="uq_catalogos_opciones_grupo_valor"),)

    grupo: Mapped[str] = mapped_column(String(60), index=True)
    valor: Mapped[str] = mapped_column(String(100))
    etiqueta: Mapped[str] = mapped_column(String(200))
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(default=True)
    # Conjunto cerrado SECCIONES_VALIDAS + NULL (básica); validado en la capa de aplicación, no
    # con CheckConstraint, porque solo aplica a los grupos con `con_seccion_acceso=True`
    # (ADR-0013, sección 5.1). Inmutable tras la creación.
    seccion_acceso: Mapped[str | None] = mapped_column(String(20), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=True)


class ConfiguracionParametro(Base):
    __tablename__ = "configuracion_sistema"

    clave: Mapped[str] = mapped_column(String(100), primary_key=True)
    valor: Mapped[str | None] = mapped_column(Text, nullable=True)
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=True)
