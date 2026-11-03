"""Inventario del Hogar: Repositorios (persistencia).

Camas, muebles, personas que viven y red de apoyo.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import HogarConviviente, HogarRedApoyo, InventarioItem


class InventarioItemRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, item: InventarioItem) -> InventarioItem:
        self.session.add(item)
        self.session.commit()
        return item

    def por_id(self, item_id: uuid.UUID) -> InventarioItem | None:
        return self.session.get(InventarioItem, item_id)

    def listar(self, hogar_id: uuid.UUID | None = None) -> list[InventarioItem]:
        consulta = select(InventarioItem)
        if hogar_id is not None:
            consulta = consulta.where(InventarioItem.hogar_id == hogar_id)
        return list(self.session.scalars(consulta.order_by(InventarioItem.created_at)))

    def guardar(self, item: InventarioItem) -> InventarioItem:
        self.session.commit()
        return item


class HogarConvivienteRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, conviviente: HogarConviviente) -> HogarConviviente:
        self.session.add(conviviente)
        self.session.commit()
        return conviviente

    def por_id(self, conviviente_id: uuid.UUID) -> HogarConviviente | None:
        return self.session.get(HogarConviviente, conviviente_id)

    def listar(self, hogar_id: uuid.UUID | None = None) -> list[HogarConviviente]:
        consulta = select(HogarConviviente)
        if hogar_id is not None:
            consulta = consulta.where(HogarConviviente.hogar_id == hogar_id)
        return list(self.session.scalars(consulta.order_by(HogarConviviente.created_at)))

    def guardar(self, conviviente: HogarConviviente) -> HogarConviviente:
        self.session.commit()
        return conviviente


class HogarRedApoyoRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, contacto: HogarRedApoyo) -> HogarRedApoyo:
        self.session.add(contacto)
        self.session.commit()
        return contacto

    def por_id(self, contacto_id: uuid.UUID) -> HogarRedApoyo | None:
        return self.session.get(HogarRedApoyo, contacto_id)

    def listar(self, hogar_id: uuid.UUID | None = None) -> list[HogarRedApoyo]:
        consulta = select(HogarRedApoyo)
        if hogar_id is not None:
            consulta = consulta.where(HogarRedApoyo.hogar_id == hogar_id)
        return list(self.session.scalars(consulta.order_by(HogarRedApoyo.created_at)))

    def guardar(self, contacto: HogarRedApoyo) -> HogarRedApoyo:
        self.session.commit()
        return contacto
