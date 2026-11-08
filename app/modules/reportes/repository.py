"""Reportes: Repositorios (persistencia).

Solo `InformeGenerado` (trazabilidad de exportaciones) tiene persistencia propia; los cuatro
niveles de reporte en pantalla son agregados de solo lectura sobre datos de otros módulos,
resueltos en la capa de aplicación.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import InformeGenerado


class InformeGeneradoRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, informe: InformeGenerado) -> InformeGenerado:
        self.session.add(informe)
        self.session.commit()
        return informe

    def por_id(self, informe_id: uuid.UUID) -> InformeGenerado | None:
        return self.session.get(InformeGenerado, informe_id)

    def listar_todos(self) -> list[InformeGenerado]:
        return list(self.session.scalars(select(InformeGenerado).order_by(InformeGenerado.generado_en.desc())))

    def listar_por_usuario(self, usuario_id: uuid.UUID) -> list[InformeGenerado]:
        consulta = (
            select(InformeGenerado)
            .where(InformeGenerado.usuario_id == usuario_id)
            .order_by(InformeGenerado.generado_en.desc())
        )
        return list(self.session.scalars(consulta))
