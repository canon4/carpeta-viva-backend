"""Inventario del Hogar: Casos de uso.

Camas, muebles, personas que viven y red de apoyo. Autorización por hogar (ADR-0009, sección 0
y 3): `zonas_hogares.application.puede_ver_hogar`/`puede_gestionar_hogar`, sin excepción por
tipo. Nunca se borra físico: `InventarioItem` se marca `retirado`, `HogarConviviente`/
`HogarRedApoyo` se marcan `activo=false`.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido
from app.modules.zonas_hogares.application import puede_gestionar_hogar, puede_ver_hogar

from .models import HogarConviviente, HogarRedApoyo, InventarioItem
from .repository import HogarConvivienteRepository, HogarRedApoyoRepository, InventarioItemRepository
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
    item = InventarioItem(
        hogar_id=datos.hogar_id,
        tipo=datos.tipo,
        descripcion=datos.descripcion,
        cantidad=datos.cantidad,
        estado=datos.estado,
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
    if datos.descripcion is not None:
        item.descripcion = datos.descripcion
    if datos.cantidad is not None:
        item.cantidad = datos.cantidad
    if datos.estado is not None:
        item.estado = datos.estado
    item = InventarioItemRepository(session).guardar(item)
    registrar_acceso(session, accion="inventario_item_actualizado", usuario_id=usuario.id, recurso=str(item.id))
    return item


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
