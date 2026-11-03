"""Menores y Expedientes: Repositorios (persistencia).

Carpeta digital de cada menor: datos personales, padres, historial médico y psicosocial, estado.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Menor, MenorFamiliar, MenorHistory, PermisoExpediente


class MenorRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, menor: Menor) -> Menor:
        self.session.add(menor)
        self.session.commit()
        return menor

    def por_id(self, menor_id: uuid.UUID) -> Menor | None:
        return self.session.get(Menor, menor_id)

    def listar(self, estado: str | None = None) -> list[Menor]:
        consulta = select(Menor)
        if estado is not None:
            consulta = consulta.where(Menor.estado_actual == estado)
        return list(self.session.scalars(consulta.order_by(Menor.created_at)))

    def guardar(self, menor: Menor) -> Menor:
        self.session.commit()
        return menor


class MenorHistoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, entrada: MenorHistory) -> MenorHistory:
        self.session.add(entrada)
        return entrada

    def listar_por_menor(self, menor_id: uuid.UUID) -> list[MenorHistory]:
        consulta = select(MenorHistory).where(MenorHistory.menor_id == menor_id).order_by(MenorHistory.version.desc())
        return list(self.session.scalars(consulta))


class MenorFamiliarRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, familiar: MenorFamiliar) -> MenorFamiliar:
        self.session.add(familiar)
        self.session.commit()
        return familiar

    def listar_por_menor(self, menor_id: uuid.UUID) -> list[MenorFamiliar]:
        consulta = select(MenorFamiliar).where(MenorFamiliar.menor_id == menor_id).order_by(MenorFamiliar.created_at)
        return list(self.session.scalars(consulta))


class PermisoExpedienteRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, permiso: PermisoExpediente) -> PermisoExpediente:
        self.session.add(permiso)
        self.session.commit()
        return permiso

    def por_id(self, permiso_id: uuid.UUID) -> PermisoExpediente | None:
        return self.session.get(PermisoExpediente, permiso_id)

    def buscar(self, menor_id: uuid.UUID, seccion: str, usuario_id: uuid.UUID) -> PermisoExpediente | None:
        consulta = select(PermisoExpediente).where(
            PermisoExpediente.menor_id == menor_id,
            PermisoExpediente.seccion == seccion,
            PermisoExpediente.usuario_id == usuario_id,
        )
        return self.session.scalars(consulta).first()

    def listar_por_menor(self, menor_id: uuid.UUID) -> list[PermisoExpediente]:
        consulta = select(PermisoExpediente).where(PermisoExpediente.menor_id == menor_id)
        return list(self.session.scalars(consulta))

    def secciones_activas(self, menor_id: uuid.UUID, usuario_id: uuid.UUID) -> set[str]:
        consulta = select(PermisoExpediente.seccion).where(
            PermisoExpediente.menor_id == menor_id,
            PermisoExpediente.usuario_id == usuario_id,
            PermisoExpediente.activo.is_(True),
        )
        return set(self.session.scalars(consulta))

    def listar_activos_de_usuario(self, menor_id: uuid.UUID, usuario_id: uuid.UUID) -> list[PermisoExpediente]:
        consulta = select(PermisoExpediente).where(
            PermisoExpediente.menor_id == menor_id,
            PermisoExpediente.usuario_id == usuario_id,
            PermisoExpediente.activo.is_(True),
        )
        return list(self.session.scalars(consulta))

    def guardar(self, permiso: PermisoExpediente) -> PermisoExpediente:
        self.session.commit()
        return permiso
