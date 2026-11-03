"""Auditoría: Repositorios (persistencia).

Registro de solo inserción de todo acceso a datos; sin edición ni borrado.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain import FiltroAuditoria
from .models import AuditoriaAcceso


class AuditoriaRepository:
    def __init__(self, session: Session):
        self.session = session

    def listar(self, filtro: FiltroAuditoria) -> list[AuditoriaAcceso]:
        consulta = select(AuditoriaAcceso)
        if filtro.usuario_id is not None:
            consulta = consulta.where(AuditoriaAcceso.usuario_id == filtro.usuario_id)
        if filtro.accion is not None:
            consulta = consulta.where(AuditoriaAcceso.accion == filtro.accion)
        if filtro.desde is not None:
            consulta = consulta.where(AuditoriaAcceso.created_at >= filtro.desde)
        if filtro.hasta is not None:
            consulta = consulta.where(AuditoriaAcceso.created_at <= filtro.hasta)
        consulta = consulta.order_by(AuditoriaAcceso.created_at.desc()).limit(filtro.limit).offset(filtro.offset)
        return list(self.session.scalars(consulta))
