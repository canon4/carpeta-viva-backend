"""Archivo y Cierre (T3): modelos ORM (ADR-0010, sección 3.3, migración 0005).

`ExpedienteArchivo` es el lugar donde vive el estado de archivo del expediente (ADR-0007 ya
decidió que ese estado no vive en `menores`). `zona_id` queda denormalizado del último
hogar/asignación del menor para que un coordinador que ya no tiene asignación vigente pueda
igualmente listar/auditar lo de su zona histórica (y para el chequeo de alcance de zona del
coordinador exigido por la revisión de seguridad en los endpoints de `/archivo`).

No se agrega `retener_hasta`: la revisión de seguridad (sección 3.4) deja explícito que ese
campo y el endpoint de purga/anonimización son una extensión futura, "no se construye ahora,
sin base legal que lo respalde" — se deja fuera de este modelo hasta que exista esa base legal.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid

from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UuidPk

ESTADOS_EXPEDIENTE_ARCHIVO = ("activo", "archivado")
DESTINO_POR_DEFECTO = "almacenamiento local cifrado — destino externo pendiente de definir con el operador"


class ExpedienteArchivo(UuidPk, Timestamps, Base):
    __tablename__ = "expedientes_archivo"
    __table_args__ = (
        CheckConstraint(
            "estado IN (" + ", ".join(f"'{e}'" for e in ESTADOS_EXPEDIENTE_ARCHIVO) + ")",
            name="ck_expedientes_archivo_estado",
        ),
    )

    menor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("menores.id"), unique=True, index=True)
    estado: Mapped[str] = mapped_column(String(20), default="activo")
    archivado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archivado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zona_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("zonas.id"), index=True, nullable=True)
    paquete_referencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paquete_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    destino: Mapped[str] = mapped_column(String(255), default=DESTINO_POR_DEFECTO)
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
