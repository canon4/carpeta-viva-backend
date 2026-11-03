"""Asignaciones y Traslados: Repositorios (persistencia).

Vincula al menor con el hogar con fecha de inicio y fin; actas de traslado.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.zonas_hogares.models import HogarSustituto

from .models import Asignacion, AsignacionHistory


class AsignacionRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, asignacion: Asignacion) -> Asignacion:
        self.session.add(asignacion)
        return asignacion

    def por_id(self, asignacion_id: uuid.UUID) -> Asignacion | None:
        return self.session.get(Asignacion, asignacion_id)

    def vigente_por_menor(self, menor_id: uuid.UUID) -> Asignacion | None:
        consulta = select(Asignacion).where(Asignacion.menor_id == menor_id, Asignacion.estado == "vigente")
        return self.session.scalars(consulta).first()

    def listar(
        self,
        menor_id: uuid.UUID | None = None,
        hogar_id: uuid.UUID | None = None,
        zona_id: uuid.UUID | None = None,
        madre_id: uuid.UUID | None = None,
        estado: str | None = None,
    ) -> list[Asignacion]:
        consulta = select(Asignacion)
        if zona_id is not None or madre_id is not None:
            consulta = consulta.join(HogarSustituto, HogarSustituto.id == Asignacion.hogar_id)
            if zona_id is not None:
                consulta = consulta.where(HogarSustituto.zona_id == zona_id)
            if madre_id is not None:
                consulta = consulta.where(HogarSustituto.madre_id == madre_id)
        if menor_id is not None:
            consulta = consulta.where(Asignacion.menor_id == menor_id)
        if hogar_id is not None:
            consulta = consulta.where(Asignacion.hogar_id == hogar_id)
        if estado is not None:
            consulta = consulta.where(Asignacion.estado == estado)
        return list(self.session.scalars(consulta.order_by(Asignacion.fecha_inicio)))

    def guardar(self, asignacion: Asignacion) -> Asignacion:
        self.session.commit()
        return asignacion

    def commit(self) -> None:
        self.session.commit()


class AsignacionHistoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, entrada: AsignacionHistory) -> AsignacionHistory:
        self.session.add(entrada)
        return entrada

    def listar_por_asignacion(self, asignacion_id: uuid.UUID) -> list[AsignacionHistory]:
        consulta = (
            select(AsignacionHistory)
            .where(AsignacionHistory.asignacion_id == asignacion_id)
            .order_by(AsignacionHistory.version.desc())
        )
        return list(self.session.scalars(consulta))
