"""Archivo y Cierre: Repositorios (persistencia)."""
import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ExpedienteArchivo


class ExpedienteArchivoRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, expediente: ExpedienteArchivo) -> ExpedienteArchivo:
        self.session.add(expediente)
        self.session.commit()
        return expediente

    def guardar(self, expediente: ExpedienteArchivo) -> ExpedienteArchivo:
        self.session.commit()
        return expediente

    def por_id(self, expediente_id: uuid.UUID) -> ExpedienteArchivo | None:
        return self.session.get(ExpedienteArchivo, expediente_id)

    def por_menor(self, menor_id: uuid.UUID) -> ExpedienteArchivo | None:
        consulta = select(ExpedienteArchivo).where(ExpedienteArchivo.menor_id == menor_id)
        return self.session.scalars(consulta).first()

    def listar_archivados(
        self,
        zona_id: uuid.UUID | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> list[ExpedienteArchivo]:
        consulta = select(ExpedienteArchivo).where(ExpedienteArchivo.estado == "archivado")
        if zona_id is not None:
            consulta = consulta.where(ExpedienteArchivo.zona_id == zona_id)
        if desde is not None:
            consulta = consulta.where(
                ExpedienteArchivo.archivado_en >= datetime.combine(desde, time.min, tzinfo=timezone.utc)
            )
        if hasta is not None:
            consulta = consulta.where(
                ExpedienteArchivo.archivado_en <= datetime.combine(hasta, time.max, tzinfo=timezone.utc)
            )
        return list(self.session.scalars(consulta.order_by(ExpedienteArchivo.archivado_en.desc())))
