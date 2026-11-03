"""Citas y Recordatorios: repositorio (persistencia)."""
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Cita


class CitaRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, cita: Cita) -> Cita:
        self.session.add(cita)
        self.session.commit()
        return cita

    def por_id(self, cita_id: uuid.UUID) -> Cita | None:
        return self.session.get(Cita, cita_id)

    def listar(
        self,
        menor_id: uuid.UUID | None = None,
        tipo: str | None = None,
        estado: str | None = None,
    ) -> list[Cita]:
        consulta = select(Cita)
        if menor_id is not None:
            consulta = consulta.where(Cita.menor_id == menor_id)
        if tipo is not None:
            consulta = consulta.where(Cita.tipo == tipo)
        if estado is not None:
            consulta = consulta.where(Cita.estado == estado)
        return list(self.session.scalars(consulta.order_by(Cita.fecha_hora)))

    def vencidas_pendientes(self, ahora: datetime) -> list[Cita]:
        consulta = select(Cita).where(Cita.estado == "pendiente", Cita.fecha_hora < ahora)
        return list(self.session.scalars(consulta))

    def guardar(self, cita: Cita) -> Cita:
        self.session.commit()
        return cita
