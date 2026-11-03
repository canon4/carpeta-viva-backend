"""Control de Alimentos: Repositorios (persistencia).

Ingreso de cada mercado, si es perecedero y su fecha de vencimiento.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AlimentoItem


class AlimentoItemRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, item: AlimentoItem) -> AlimentoItem:
        self.session.add(item)
        self.session.commit()
        return item

    def por_id(self, item_id: uuid.UUID) -> AlimentoItem | None:
        return self.session.get(AlimentoItem, item_id)

    def listar(
        self,
        hogar_id: uuid.UUID | None = None,
        perecedero: bool | None = None,
        consumido: bool | None = None,
    ) -> list[AlimentoItem]:
        consulta = select(AlimentoItem)
        if hogar_id is not None:
            consulta = consulta.where(AlimentoItem.hogar_id == hogar_id)
        if perecedero is not None:
            consulta = consulta.where(AlimentoItem.perecedero == perecedero)
        if consumido is not None:
            consulta = consulta.where(AlimentoItem.consumido == consumido)
        return list(self.session.scalars(consulta.order_by(AlimentoItem.created_at)))

    def guardar(self, item: AlimentoItem) -> AlimentoItem:
        self.session.commit()
        return item
