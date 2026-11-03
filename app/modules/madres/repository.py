"""Madres Sustitutas: Repositorios (persistencia).

Datos de la madre sustituta: identificación, certificación y firma única.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MadreSustituta


class MadreRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, madre: MadreSustituta) -> MadreSustituta:
        self.session.add(madre)
        self.session.commit()
        return madre

    def por_id(self, madre_id: uuid.UUID) -> MadreSustituta | None:
        return self.session.get(MadreSustituta, madre_id)

    def por_usuario_id(self, usuario_id: uuid.UUID) -> MadreSustituta | None:
        return self.session.scalar(select(MadreSustituta).where(MadreSustituta.usuario_id == usuario_id))

    def listar(self) -> list[MadreSustituta]:
        return list(self.session.scalars(select(MadreSustituta).order_by(MadreSustituta.apellidos)))

    def guardar(self, madre: MadreSustituta) -> MadreSustituta:
        self.session.commit()
        return madre
