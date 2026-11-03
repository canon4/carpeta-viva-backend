"""Control de Alimentos: Casos de uso.

Ingreso de cada mercado, si es perecedero y su fecha de vencimiento. Autorización por hogar
(ADR-0009, sección 4), igual que `inventario`: `zonas_hogares.application.puede_ver_hogar`/
`puede_gestionar_hogar`. Nunca se borra físico: se marca `consumido`.
"""
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido
from app.modules.zonas_hogares.application import puede_gestionar_hogar, puede_ver_hogar

from .domain import esta_vencido, validar_perecedero
from .models import AlimentoItem
from .repository import AlimentoItemRepository
from .schemas import AlimentoItemCreate, AlimentoItemUpdate


def _item_o_404(session: Session, item_id: uuid.UUID) -> AlimentoItem:
    item = AlimentoItemRepository(session).por_id(item_id)
    if item is None:
        raise no_encontrado("Alimento no encontrado")
    return item


def crear_alimento(session: Session, usuario, datos: AlimentoItemCreate) -> AlimentoItem:
    if not puede_gestionar_hogar(session, usuario, datos.hogar_id):
        registrar_acceso(session, accion="alimento_creacion_denegada", usuario_id=usuario.id, recurso=str(datos.hogar_id))
        raise prohibido()
    validar_perecedero(datos.perecedero, datos.fecha_vencimiento)
    item = AlimentoItem(
        hogar_id=datos.hogar_id,
        descripcion=datos.descripcion,
        fecha_ingreso=datos.fecha_ingreso,
        perecedero=datos.perecedero,
        fecha_vencimiento=datos.fecha_vencimiento,
        cantidad=datos.cantidad,
        unidad=datos.unidad,
        registrado_por=usuario.id,
    )
    item = AlimentoItemRepository(session).crear(item)
    registrar_acceso(session, accion="alimento_creado", usuario_id=usuario.id, recurso=str(item.id))
    return item


def listar_alimentos(
    session: Session,
    usuario,
    hogar_id: uuid.UUID,
    perecedero: bool | None = None,
    consumido: bool | None = None,
    vencidos: bool | None = None,
) -> list[AlimentoItem]:
    if not puede_ver_hogar(session, usuario, hogar_id):
        registrar_acceso(session, accion="alimentos_listado_denegado", usuario_id=usuario.id, recurso=str(hogar_id))
        raise prohibido()
    resultado = AlimentoItemRepository(session).listar(hogar_id=hogar_id, perecedero=perecedero, consumido=consumido)
    if vencidos:
        hoy = date.today()
        resultado = [i for i in resultado if esta_vencido(i.perecedero, i.fecha_vencimiento, i.consumido, hoy)]
    registrar_acceso(session, accion="alimentos_listados", usuario_id=usuario.id, recurso=str(hogar_id))
    return resultado


def actualizar_alimento(session: Session, usuario, item_id: uuid.UUID, datos: AlimentoItemUpdate) -> AlimentoItem:
    item = _item_o_404(session, item_id)
    if not puede_gestionar_hogar(session, usuario, item.hogar_id):
        registrar_acceso(session, accion="alimento_actualizacion_denegada", usuario_id=usuario.id, recurso=str(item.id))
        raise prohibido()
    if datos.descripcion is not None:
        item.descripcion = datos.descripcion
    if datos.fecha_ingreso is not None:
        item.fecha_ingreso = datos.fecha_ingreso
    if datos.perecedero is not None:
        item.perecedero = datos.perecedero
    if datos.fecha_vencimiento is not None:
        item.fecha_vencimiento = datos.fecha_vencimiento
    validar_perecedero(item.perecedero, item.fecha_vencimiento)
    if datos.cantidad is not None:
        item.cantidad = datos.cantidad
    if datos.unidad is not None:
        item.unidad = datos.unidad
    item = AlimentoItemRepository(session).guardar(item)
    registrar_acceso(session, accion="alimento_actualizado", usuario_id=usuario.id, recurso=str(item.id))
    return item


def marcar_consumido(session: Session, usuario, item_id: uuid.UUID) -> AlimentoItem:
    item = _item_o_404(session, item_id)
    if not puede_gestionar_hogar(session, usuario, item.hogar_id):
        registrar_acceso(session, accion="alimento_consumido_denegado", usuario_id=usuario.id, recurso=str(item.id))
        raise prohibido()
    item.consumido = True
    item = AlimentoItemRepository(session).guardar(item)
    registrar_acceso(session, accion="alimento_consumido", usuario_id=usuario.id, recurso=str(item.id))
    return item
