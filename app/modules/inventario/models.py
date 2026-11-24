"""Inventario del Hogar: Modelos ORM.

Camas, muebles, personas que viven en el hogar y red de apoyo. Sin borrado físico (ADR-0009,
sección 3): `InventarioItem` se marca `retirado`, `HogarConviviente`/`HogarRedApoyo` se marcan
`activo=false`.

ADR-0014: `InventarioItem.recibido` separa el pedido (coordinador, `recibido=false`) de su
confirmación de llegada (madre/admin, `recibido=true`). `InventarioItemFoto` guarda evidencia
fotográfica de la recepción, cifrada con el mismo mecanismo que `documentos`
(`app/core/almacenamiento.py`), sin versionado.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Uuid, func
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
    # ADR-0014: False = pedido del coordinador, aún no llega. True = ya está físicamente en el
    # hogar (lo creó la madre/admin directo, o el pedido ya se confirmó). `server_default=true`
    # solo afecta a filas migradas sin valor explícito (ítems anteriores a esta ADR); la
    # aplicación siempre manda el valor explícito según el rol de quien crea.
    recibido: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class InventarioItemFoto(UuidPk, Base):
    """Evidencia fotográfica de la recepción de un ítem (ADR-0014, sección 2). Sin versionado:
    una foto subida por error se queda, no se reemplaza ni se borra físico.

    ADR-0014, sección 2.1 (revisión de `seguridad`): `declaracion_sin_menores` registra, por cada
    subida, que quien la hizo declaró que la foto no muestra a ningún NNA (mitigación de UI,
    auditable). `oculta` es el mecanismo de remediación admin-only si de todas formas una foto
    termina mostrando a un NNA sin querer: nunca se borra, se oculta (igual criterio que RF7).
    """

    __tablename__ = "inventario_item_fotos"

    item_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("inventario_items.id"), index=True)
    referencia_archivo: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    tamanio_bytes: Mapped[int] = mapped_column(Integer)
    subido_por: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    declaracion_sin_menores: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    oculta: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


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
    # ADR-0019, sección 5: una sola foto de perfil por contacto (no una galería como la evidencia
    # de inventario). Mismo mecanismo cifrado, siempre versión 1, sin historial.
    foto_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
