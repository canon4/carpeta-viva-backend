"""Configuración administrable: repositorios (persistencia)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CatalogoOpcion, ConfiguracionParametro


class CatalogoOpcionRepository:
    def __init__(self, session: Session):
        self.session = session

    def listar(self, grupo: str, solo_activas: bool = True) -> list[CatalogoOpcion]:
        consulta = select(CatalogoOpcion).where(CatalogoOpcion.grupo == grupo)
        if solo_activas:
            consulta = consulta.where(CatalogoOpcion.activo.is_(True))
        consulta = consulta.order_by(CatalogoOpcion.orden, CatalogoOpcion.etiqueta)
        return list(self.session.scalars(consulta))

    def contar_todas(self, grupo: str) -> int:
        return len(list(self.session.scalars(select(CatalogoOpcion).where(CatalogoOpcion.grupo == grupo))))

    def por_grupo_y_valor(self, grupo: str, valor: str) -> CatalogoOpcion | None:
        consulta = select(CatalogoOpcion).where(CatalogoOpcion.grupo == grupo, CatalogoOpcion.valor == valor)
        return self.session.scalars(consulta).first()

    def crear(self, opcion: CatalogoOpcion) -> CatalogoOpcion:
        self.session.add(opcion)
        self.session.commit()
        return opcion

    def guardar(self, opcion: CatalogoOpcion) -> CatalogoOpcion:
        self.session.commit()
        return opcion


class ConfiguracionParametroRepository:
    def __init__(self, session: Session):
        self.session = session

    def por_clave(self, clave: str) -> ConfiguracionParametro | None:
        return self.session.get(ConfiguracionParametro, clave)

    def crear(self, parametro: ConfiguracionParametro) -> ConfiguracionParametro:
        self.session.add(parametro)
        self.session.commit()
        return parametro

    def guardar(self, parametro: ConfiguracionParametro) -> ConfiguracionParametro:
        self.session.commit()
        return parametro
