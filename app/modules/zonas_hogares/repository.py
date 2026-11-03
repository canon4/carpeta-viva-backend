"""Zonas y Hogares: Repositorios (persistencia).

Organiza los hogares sustitutos por zona y guarda los datos de cada hogar.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import HogarSustituto, Zona


class ZonaRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, zona: Zona) -> Zona:
        self.session.add(zona)
        self.session.commit()
        return zona

    def por_id(self, zona_id: uuid.UUID) -> Zona | None:
        return self.session.get(Zona, zona_id)

    def listar(self) -> list[Zona]:
        return list(self.session.scalars(select(Zona).order_by(Zona.nombre)))

    def guardar(self, zona: Zona) -> Zona:
        self.session.commit()
        return zona


class HogarRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, hogar: HogarSustituto) -> HogarSustituto:
        self.session.add(hogar)
        self.session.commit()
        return hogar

    def por_id(self, hogar_id: uuid.UUID) -> HogarSustituto | None:
        return self.session.get(HogarSustituto, hogar_id)

    def listar(self, zona_id: uuid.UUID | None = None) -> list[HogarSustituto]:
        consulta = select(HogarSustituto)
        if zona_id is not None:
            consulta = consulta.where(HogarSustituto.zona_id == zona_id)
        return list(self.session.scalars(consulta.order_by(HogarSustituto.created_at)))

    def guardar(self, hogar: HogarSustituto) -> HogarSustituto:
        self.session.commit()
        return hogar
