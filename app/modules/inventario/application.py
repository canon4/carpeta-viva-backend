"""Inventario del Hogar: Casos de uso.

Camas, muebles, personas que viven y red de apoyo. Autorización por hogar (ADR-0009, sección 0
y 3): `zonas_hogares.application.puede_ver_hogar`/`puede_gestionar_hogar`, sin excepción por
tipo. Nunca se borra físico: `InventarioItem` se marca `retirado`, `HogarConviviente`/
`HogarRedApoyo` se marcan `activo=false`.

ADR-0014: separa el pedido (coordinador) de su recepción (madre/admin). `crear_item` decide
`recibido` según el rol de quien crea, no según un campo del cliente. `actualizar_item` exige
coordinador/admin e ítem aún no recibido para tocar tipo/descripción/cantidad del pedido.
`confirmar_recepcion_item` es el evento, una sola vez, de marcar la llegada con su estado físico.
Las fotos de evidencia reutilizan `app/core/almacenamiento.py` (mismo cifrado que `documentos`,
ADR-0008), sin versionado.
"""
import uuid

from sqlalchemy.orm import Session

from app.core import almacenamiento
from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido
from app.modules.auth.domain import Rol
from app.modules.zonas_hogares.application import puede_gestionar_hogar, puede_ver_hogar

from .domain import FOTO_TAMANIO_MAXIMO_BYTES, FOTOS_MAXIMO_POR_ITEM, MIME_FOTOS_PERMITIDOS
from .models import HogarConviviente, HogarRedApoyo, InventarioItem, InventarioItemFoto
from .repository import (
    HogarConvivienteRepository,
    HogarRedApoyoRepository,
    InventarioItemFotoRepository,
    InventarioItemRepository,
)
from .schemas import (
    ConvivienteCreate,
    ConvivienteUpdate,
    InventarioItemCreate,
    InventarioItemUpdate,
    RedApoyoCreate,
    RedApoyoUpdate,
)

# ---------------------------------------------------------------------------
# Items (camas, muebles, otro)
# ---------------------------------------------------------------------------

def crear_item(session: Session, usuario, datos: InventarioItemCreate) -> InventarioItem:
    if not puede_gestionar_hogar(session, usuario, datos.hogar_id):
        registrar_acceso(session, accion="inventario_item_creacion_denegada", usuario_id=usuario.id, recurso=str(datos.hogar_id))
        raise prohibido()
    # ADR-0014, sección 1: `recibido` depende de quién crea, nunca de un campo del cliente (para
    # que no se pueda fingir una entrega que no pasó por la madre). El coordinador registra un
    # pedido (`recibido=False`); el `estado` que mande se ignora porque todavía no existe nada
    # físico que calificar. Madre y admin registran algo que ya está en el hogar.
    es_pedido = usuario.rol == Rol.COORDINADOR.value
    item = InventarioItem(
        hogar_id=datos.hogar_id,
        tipo=datos.tipo,
        descripcion=datos.descripcion,
        cantidad=datos.cantidad,
        estado="bueno" if es_pedido else datos.estado,
        recibido=not es_pedido,
        registrado_por=usuario.id,
    )
    item = InventarioItemRepository(session).crear(item)
    registrar_acceso(session, accion="inventario_item_creado", usuario_id=usuario.id, recurso=str(item.id))
    return item


def listar_items(session: Session, usuario, hogar_id: uuid.UUID) -> list[InventarioItem]:
    if not puede_ver_hogar(session, usuario, hogar_id):
        registrar_acceso(session, accion="inventario_items_listado_denegado", usuario_id=usuario.id, recurso=str(hogar_id))
        raise prohibido()
    resultado = InventarioItemRepository(session).listar(hogar_id=hogar_id)
    registrar_acceso(session, accion="inventario_items_listados", usuario_id=usuario.id, recurso=str(hogar_id))
    return resultado


def _item_o_404(session: Session, item_id: uuid.UUID) -> InventarioItem:
    item = InventarioItemRepository(session).por_id(item_id)
    if item is None:
        raise no_encontrado("Ítem de inventario no encontrado")
    return item


def actualizar_item(session: Session, usuario, item_id: uuid.UUID, datos: InventarioItemUpdate) -> InventarioItem:
    item = _item_o_404(session, item_id)
    if not puede_gestionar_hogar(session, usuario, item.hogar_id):
        registrar_acceso(session, accion="inventario_item_actualizacion_denegada", usuario_id=usuario.id, recurso=str(item.id))
        raise prohibido()
    # ADR-0014, sección 1: editar tipo/descripción/cantidad es editar el pedido, no el estado
    # físico; solo coordinador/admin y solo mientras no se haya confirmado la recepción.
    toca_pedido = datos.tipo is not None or datos.descripcion is not None or datos.cantidad is not None
    if toca_pedido:
        if usuario.rol not in (Rol.COORDINADOR.value, Rol.ADMIN.value):
            registrar_acceso(
                session, accion="inventario_item_actualizacion_denegada", usuario_id=usuario.id, recurso=str(item.id)
            )
            raise prohibido()
        if item.recibido:
            raise ValueError("El ítem ya fue recibido; no se puede editar el pedido original")
    if datos.tipo is not None:
        item.tipo = datos.tipo
    if datos.descripcion is not None:
        item.descripcion = datos.descripcion
    if datos.cantidad is not None:
        item.cantidad = datos.cantidad
    if datos.estado is not None:
        item.estado = datos.estado
    item = InventarioItemRepository(session).guardar(item)
    registrar_acceso(session, accion="inventario_item_actualizado", usuario_id=usuario.id, recurso=str(item.id))
    return item


def confirmar_recepcion_item(session: Session, usuario, item_id: uuid.UUID, estado: str) -> InventarioItem:
    """ADR-0014, sección 1: confirmar que un pedido llegó, con su estado físico. Solo madre (del
    hogar) o admin; un evento que pasa una sola vez por ítem."""
    item = _item_o_404(session, item_id)
    if not puede_gestionar_hogar(session, usuario, item.hogar_id):
        registrar_acceso(
            session, accion="inventario_item_recepcion_denegada", usuario_id=usuario.id, recurso=str(item.id)
        )
        raise prohibido()
    if usuario.rol not in (Rol.MADRE.value, Rol.ADMIN.value):
        registrar_acceso(
            session, accion="inventario_item_recepcion_denegada", usuario_id=usuario.id, recurso=str(item.id)
        )
        raise prohibido()
    if item.recibido:
        raise ValueError("El ítem ya estaba marcado como recibido")
    item.estado = estado
    item.recibido = True
    item = InventarioItemRepository(session).guardar(item)
    registrar_acceso(
        session, accion="inventario_item_recepcion_confirmada", usuario_id=usuario.id, recurso=str(item.id)
    )
    return item


# ---------------------------------------------------------------------------
# Fotos de evidencia de recepción
# ---------------------------------------------------------------------------

def subir_foto_item(
    session: Session, usuario, item_id: uuid.UUID, contenido: bytes, mime_type: str, nombre_archivo: str
) -> InventarioItemFoto:
    item = _item_o_404(session, item_id)
    if not puede_gestionar_hogar(session, usuario, item.hogar_id):
        registrar_acceso(session, accion="inventario_foto_subida_denegada", usuario_id=usuario.id, recurso=str(item.id))
        raise prohibido()
    if usuario.rol not in (Rol.MADRE.value, Rol.ADMIN.value):
        registrar_acceso(session, accion="inventario_foto_subida_denegada", usuario_id=usuario.id, recurso=str(item.id))
        raise prohibido()
    if mime_type not in MIME_FOTOS_PERMITIDOS:
        raise ValueError("Tipo de imagen no permitido; use JPEG, PNG o WEBP")
    if len(contenido) == 0:
        raise ValueError("La foto está vacía")
    if len(contenido) > FOTO_TAMANIO_MAXIMO_BYTES:
        raise ValueError(f"La foto supera el tamaño máximo permitido ({FOTO_TAMANIO_MAXIMO_BYTES // (1024 * 1024)} MB)")
    if InventarioItemFotoRepository(session).contar(item_id) >= FOTOS_MAXIMO_POR_ITEM:
        raise ValueError(f"Se alcanzó el máximo de {FOTOS_MAXIMO_POR_ITEM} fotos por ítem")

    foto_id = uuid.uuid4()
    referencia, _hash = almacenamiento.guardar(item.hogar_id, foto_id, 1, contenido)
    foto = InventarioItemFoto(
        id=foto_id,
        item_id=item_id,
        referencia_archivo=referencia,
        mime_type=mime_type,
        tamanio_bytes=len(contenido),
        subido_por=usuario.id,
    )
    foto = InventarioItemFotoRepository(session).crear(foto)
    registrar_acceso(session, accion="inventario_foto_subida", usuario_id=usuario.id, recurso=str(foto.id))
    return foto


def listar_fotos_item(session: Session, usuario, item_id: uuid.UUID) -> list[InventarioItemFoto]:
    item = _item_o_404(session, item_id)
    if not puede_ver_hogar(session, usuario, item.hogar_id):
        registrar_acceso(session, accion="inventario_fotos_listado_denegado", usuario_id=usuario.id, recurso=str(item.id))
        raise prohibido()
    resultado = InventarioItemFotoRepository(session).listar(item_id)
    registrar_acceso(session, accion="inventario_fotos_listadas", usuario_id=usuario.id, recurso=str(item.id))
    return resultado


def obtener_foto_item(session: Session, usuario, item_id: uuid.UUID, foto_id: uuid.UUID) -> tuple[InventarioItemFoto, bytes]:
    item = _item_o_404(session, item_id)
    if not puede_ver_hogar(session, usuario, item.hogar_id):
        registrar_acceso(session, accion="inventario_foto_consulta_denegada", usuario_id=usuario.id, recurso=str(item.id))
        raise prohibido()
    foto = InventarioItemFotoRepository(session).por_id(foto_id)
    if foto is None or foto.item_id != item_id:
        raise no_encontrado("Foto no encontrada")
    contenido = almacenamiento.leer(foto.referencia_archivo)
    registrar_acceso(session, accion="inventario_foto_consultada", usuario_id=usuario.id, recurso=str(foto.id))
    return foto, contenido


# ---------------------------------------------------------------------------
# Convivientes
# ---------------------------------------------------------------------------

def crear_conviviente(session: Session, usuario, datos: ConvivienteCreate) -> HogarConviviente:
    if not puede_gestionar_hogar(session, usuario, datos.hogar_id):
        registrar_acceso(session, accion="conviviente_creacion_denegada", usuario_id=usuario.id, recurso=str(datos.hogar_id))
        raise prohibido()
    conviviente = HogarConviviente(
        hogar_id=datos.hogar_id,
        nombres=datos.nombres,
        relacion_con_madre=datos.relacion_con_madre,
        fecha_desde=datos.fecha_desde,
        observaciones=datos.observaciones,
    )
    conviviente = HogarConvivienteRepository(session).crear(conviviente)
    registrar_acceso(session, accion="conviviente_creado", usuario_id=usuario.id, recurso=str(conviviente.id))
    return conviviente


def listar_convivientes(session: Session, usuario, hogar_id: uuid.UUID) -> list[HogarConviviente]:
    if not puede_ver_hogar(session, usuario, hogar_id):
        registrar_acceso(session, accion="convivientes_listado_denegado", usuario_id=usuario.id, recurso=str(hogar_id))
        raise prohibido()
    resultado = HogarConvivienteRepository(session).listar(hogar_id=hogar_id)
    registrar_acceso(session, accion="convivientes_listados", usuario_id=usuario.id, recurso=str(hogar_id))
    return resultado


def _conviviente_o_404(session: Session, conviviente_id: uuid.UUID) -> HogarConviviente:
    conviviente = HogarConvivienteRepository(session).por_id(conviviente_id)
    if conviviente is None:
        raise no_encontrado("Conviviente no encontrado")
    return conviviente


def actualizar_conviviente(session: Session, usuario, conviviente_id: uuid.UUID, datos: ConvivienteUpdate) -> HogarConviviente:
    conviviente = _conviviente_o_404(session, conviviente_id)
    if not puede_gestionar_hogar(session, usuario, conviviente.hogar_id):
        registrar_acceso(session, accion="conviviente_actualizacion_denegada", usuario_id=usuario.id, recurso=str(conviviente.id))
        raise prohibido()
    if datos.nombres is not None:
        conviviente.nombres = datos.nombres
    if datos.relacion_con_madre is not None:
        conviviente.relacion_con_madre = datos.relacion_con_madre
    if datos.fecha_desde is not None:
        conviviente.fecha_desde = datos.fecha_desde
    if datos.observaciones is not None:
        conviviente.observaciones = datos.observaciones
    if datos.activo is not None:
        conviviente.activo = datos.activo
    conviviente = HogarConvivienteRepository(session).guardar(conviviente)
    registrar_acceso(session, accion="conviviente_actualizado", usuario_id=usuario.id, recurso=str(conviviente.id))
    return conviviente


# ---------------------------------------------------------------------------
# Red de apoyo
# ---------------------------------------------------------------------------

def crear_red_apoyo(session: Session, usuario, datos: RedApoyoCreate) -> HogarRedApoyo:
    if not puede_gestionar_hogar(session, usuario, datos.hogar_id):
        registrar_acceso(session, accion="red_apoyo_creacion_denegada", usuario_id=usuario.id, recurso=str(datos.hogar_id))
        raise prohibido()
    contacto = HogarRedApoyo(
        hogar_id=datos.hogar_id,
        nombres=datos.nombres,
        relacion=datos.relacion,
        telefono=datos.telefono,
        observaciones=datos.observaciones,
    )
    contacto = HogarRedApoyoRepository(session).crear(contacto)
    registrar_acceso(session, accion="red_apoyo_creado", usuario_id=usuario.id, recurso=str(contacto.id))
    return contacto


def listar_red_apoyo(session: Session, usuario, hogar_id: uuid.UUID) -> list[HogarRedApoyo]:
    if not puede_ver_hogar(session, usuario, hogar_id):
        registrar_acceso(session, accion="red_apoyo_listado_denegado", usuario_id=usuario.id, recurso=str(hogar_id))
        raise prohibido()
    resultado = HogarRedApoyoRepository(session).listar(hogar_id=hogar_id)
    registrar_acceso(session, accion="red_apoyo_listada", usuario_id=usuario.id, recurso=str(hogar_id))
    return resultado


def _red_apoyo_o_404(session: Session, contacto_id: uuid.UUID) -> HogarRedApoyo:
    contacto = HogarRedApoyoRepository(session).por_id(contacto_id)
    if contacto is None:
        raise no_encontrado("Contacto de red de apoyo no encontrado")
    return contacto


def actualizar_red_apoyo(session: Session, usuario, contacto_id: uuid.UUID, datos: RedApoyoUpdate) -> HogarRedApoyo:
    contacto = _red_apoyo_o_404(session, contacto_id)
    if not puede_gestionar_hogar(session, usuario, contacto.hogar_id):
        registrar_acceso(session, accion="red_apoyo_actualizacion_denegada", usuario_id=usuario.id, recurso=str(contacto.id))
        raise prohibido()
    if datos.nombres is not None:
        contacto.nombres = datos.nombres
    if datos.relacion is not None:
        contacto.relacion = datos.relacion
    if datos.telefono is not None:
        contacto.telefono = datos.telefono
    if datos.observaciones is not None:
        contacto.observaciones = datos.observaciones
    if datos.activo is not None:
        contacto.activo = datos.activo
    contacto = HogarRedApoyoRepository(session).guardar(contacto)
    registrar_acceso(session, accion="red_apoyo_actualizada", usuario_id=usuario.id, recurso=str(contacto.id))
    return contacto
