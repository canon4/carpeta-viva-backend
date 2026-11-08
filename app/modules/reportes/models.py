"""Reportes (módulo 12): modelos ORM (ADR-0010, sección 2, migración 0005).

No confundir con `Reporte` de `documentos/models.py` (informe clínico de seguimiento,
ADR-0007/0008): este módulo nuevo se llama `reportes` como módulo de backend/frontend
(coincide con `docs/modulos.md`), pero la tabla nueva usa el nombre `informes_generados`
para no colisionar con la clase `Reporte` ya existente.

Solo se escribe fila cuando el informe se **exporta** (`POST /reportes/exportar`); las
consultas de solo pantalla no se persisten aquí (quedan en `auditoria_accesos`). El hueco de
autorización corregido por seguridad (revalidar permisos vigentes al **descargar**, no solo
al generar) es responsabilidad de la capa de aplicación, no de este modelo de datos.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base, UuidPk

NIVELES_INFORME = ("general", "zona", "menor", "madre")
FORMATOS_INFORME = ("json", "pdf", "csv")


class InformeGenerado(UuidPk, Base):
    __tablename__ = "informes_generados"
    __table_args__ = (
        CheckConstraint("nivel IN (" + ", ".join(f"'{n}'" for n in NIVELES_INFORME) + ")", name="ck_informes_generados_nivel"),
        CheckConstraint(
            "formato IN (" + ", ".join(f"'{f}'" for f in FORMATOS_INFORME) + ")", name="ck_informes_generados_formato"
        ),
    )

    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"), index=True)
    nivel: Mapped[str] = mapped_column(String(20))
    filtros: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=dict)
    formato: Mapped[str] = mapped_column(String(10))
    referencia_archivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
