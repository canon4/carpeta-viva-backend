"""Profesionales: Repositorios (persistencia).

Datos del personal profesional (defensor, psicosocial, nutrición, trabajo social).
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MenorProfesional, Profesional


class ProfesionalRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, profesional: Profesional) -> Profesional:
        self.session.add(profesional)
        self.session.commit()
        return profesional

    def por_id(self, profesional_id: uuid.UUID) -> Profesional | None:
        return self.session.get(Profesional, profesional_id)

    def por_usuario_id(self, usuario_id: uuid.UUID) -> Profesional | None:
        consulta = select(Profesional).where(Profesional.usuario_id == usuario_id)
        return self.session.scalars(consulta).first()

    def listar(self, cargo: str | None = None) -> list[Profesional]:
        consulta = select(Profesional)
        if cargo is not None:
            consulta = consulta.where(Profesional.cargo == cargo)
        return list(self.session.scalars(consulta.order_by(Profesional.apellidos)))

    def guardar(self, profesional: Profesional) -> Profesional:
        self.session.commit()
        return profesional


class MenorProfesionalRepository:
    def __init__(self, session: Session):
        self.session = session

    def asignacion(self, menor_id: uuid.UUID, profesional_id: uuid.UUID) -> MenorProfesional | None:
        consulta = select(MenorProfesional).where(
            MenorProfesional.menor_id == menor_id,
            MenorProfesional.profesional_id == profesional_id,
        )
        return self.session.scalars(consulta).first()

    def listar_por_menor(self, menor_id: uuid.UUID) -> list[MenorProfesional]:
        consulta = select(MenorProfesional).where(MenorProfesional.menor_id == menor_id)
        return list(self.session.scalars(consulta))

    def listar_por_profesional(self, profesional_id: uuid.UUID) -> list[MenorProfesional]:
        consulta = select(MenorProfesional).where(MenorProfesional.profesional_id == profesional_id)
        return list(self.session.scalars(consulta))
