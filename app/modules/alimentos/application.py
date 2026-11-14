"""Control de Alimentos: Casos de uso.

Ingreso de cada mercado, si es perecedero y su fecha de vencimiento. Autorización por hogar
(ADR-0009, sección 4), igual que `inventario`: `zonas_hogares.application.puede_ver_hogar`/
`puede_gestionar_hogar`. Nunca se borra físico: se marca `consumido`.

ADR-0014, sección 4: checklist reutilizable (el "producto del mercado"), sin distinción de rol
adicional a la que ya tiene el módulo: misma `puede_ver_hogar`/`puede_gestionar_hogar`.
"""
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido
from app.modules.zonas_hogares.application import puede_gestionar_hogar, puede_ver_hogar

from .domain import esta_vencido, validar_perecedero
from .models import AlimentoChecklistItem, AlimentoItem
from .repository import AlimentoChecklistItemRepository, AlimentoItemRepository
from .schemas import (
    AlimentoChecklistComprar,
    AlimentoChecklistItemCreate,
    AlimentoChecklistItemUpdate,
    AlimentoItemCreate,
    AlimentoItemUpdate,
)


def _item_o_404(session: Session, item_id: uuid.UUID) -> AlimentoItem:
    item = AlimentoItemRepository(session).por_id(item_id)
    if item is None:
        raise no_encontrado("Alimento no encontrado")
    return item


def _checklist_item_o_404(session: Session, checklist_item_id: uuid.UUID) -> AlimentoChecklistItem:
    item = AlimentoChecklistItemRepository(session).por_id(checklist_item_id)
    if item is None:
        raise no_encontrado("Producto del checklist no encontrado")
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


# ---------------------------------------------------------------------------
# Checklist reutilizable (ADR-0014, sección 4)
# ---------------------------------------------------------------------------

def crear_checklist_item(session: Session, usuario, datos: AlimentoChecklistItemCreate) -> AlimentoChecklistItem:
    if not puede_gestionar_hogar(session, usuario, datos.hogar_id):
        registrar_acceso(session, accion="alimento_checklist_creacion_denegada", usuario_id=usuario.id, recurso=str(datos.hogar_id))
        raise prohibido()
    item = AlimentoChecklistItem(
        hogar_id=datos.hogar_id,
        descripcion=datos.descripcion,
        perecedero=datos.perecedero,
        unidad_por_defecto=datos.unidad_por_defecto,
        creado_por=usuario.id,
    )
    item = AlimentoChecklistItemRepository(session).crear(item)
    registrar_acceso(session, accion="alimento_checklist_creado", usuario_id=usuario.id, recurso=str(item.id))
    return item


def listar_checklist_items(
    session: Session, usuario, hogar_id: uuid.UUID, incluir_inactivos: bool = False
) -> list[AlimentoChecklistItem]:
    if not puede_ver_hogar(session, usuario, hogar_id):
        registrar_acceso(session, accion="alimento_checklist_listado_denegado", usuario_id=usuario.id, recurso=str(hogar_id))
        raise prohibido()
    resultado = AlimentoChecklistItemRepository(session).listar(hogar_id=hogar_id, solo_activos=not incluir_inactivos)
    registrar_acceso(session, accion="alimento_checklist_listado", usuario_id=usuario.id, recurso=str(hogar_id))
    return resultado


def actualizar_checklist_item(
    session: Session, usuario, checklist_item_id: uuid.UUID, datos: AlimentoChecklistItemUpdate
) -> AlimentoChecklistItem:
    item = _checklist_item_o_404(session, checklist_item_id)
    if not puede_gestionar_hogar(session, usuario, item.hogar_id):
        registrar_acceso(session, accion="alimento_checklist_actualizacion_denegada", usuario_id=usuario.id, recurso=str(item.id))
        raise prohibido()
    if datos.descripcion is not None:
        item.descripcion = datos.descripcion
    if datos.unidad_por_defecto is not None:
        item.unidad_por_defecto = datos.unidad_por_defecto
    if datos.activo is not None:
        item.activo = datos.activo
    item = AlimentoChecklistItemRepository(session).guardar(item)
    registrar_acceso(session, accion="alimento_checklist_actualizado", usuario_id=usuario.id, recurso=str(item.id))
    return item


def comprar_de_checklist(
    session: Session, usuario, checklist_item_id: uuid.UUID, datos: AlimentoChecklistComprar
) -> AlimentoItem:
    """Atajo que pidió el usuario: crea un `AlimentoItem` nuevo (historial completo, nunca
    sobrescribe la compra anterior) tomando `descripcion`/`perecedero` del checklist."""
    checklist_item = _checklist_item_o_404(session, checklist_item_id)
    if not puede_gestionar_hogar(session, usuario, checklist_item.hogar_id):
        registrar_acceso(
            session, accion="alimento_checklist_compra_denegada", usuario_id=usuario.id, recurso=str(checklist_item.id)
        )
        raise prohibido()
    validar_perecedero(checklist_item.perecedero, datos.fecha_vencimiento)
    item = AlimentoItem(
        hogar_id=checklist_item.hogar_id,
        descripcion=checklist_item.descripcion,
        fecha_ingreso=datos.fecha_ingreso,
        perecedero=checklist_item.perecedero,
        fecha_vencimiento=datos.fecha_vencimiento,
        cantidad=datos.cantidad,
        unidad=datos.unidad if datos.unidad is not None else checklist_item.unidad_por_defecto,
        checklist_item_id=checklist_item.id,
        registrado_por=usuario.id,
    )
    item = AlimentoItemRepository(session).crear(item)
    registrar_acceso(session, accion="alimento_checklist_comprado", usuario_id=usuario.id, recurso=str(item.id))
    return item
