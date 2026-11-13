"""Alertas y Evasiones: repositorios (persistencia)."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Alerta, AlertaDestinatario, ConfiguracionAlertas


class ConfiguracionAlertasRepository:
    """Fila única (id=1). La migración 0008 la deja sembrada en Postgres; se crea sola aquí si
    falta (p. ej. en pruebas, que arman el esquema con `Base.metadata.create_all` y nunca
    corren las migraciones) para que un `admin` nunca se tope con un error por esto."""

    def __init__(self, session: Session):
        self.session = session

    def obtener(self) -> ConfiguracionAlertas:
        configuracion = self.session.get(ConfiguracionAlertas, 1)
        if configuracion is None:
            configuracion = ConfiguracionAlertas(id=1, telefono_policia_infancia=None)
            self.session.add(configuracion)
            self.session.commit()
        return configuracion

    def guardar(self, configuracion: ConfiguracionAlertas) -> ConfiguracionAlertas:
        self.session.commit()
        return configuracion


class AlertaRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, alerta: Alerta) -> Alerta:
        self.session.add(alerta)
        self.session.commit()
        return alerta

    def por_id(self, alerta_id: uuid.UUID) -> Alerta | None:
        return self.session.get(Alerta, alerta_id)

    def listar(
        self,
        menor_id: uuid.UUID | None = None,
        tipo: str | None = None,
        estado: str | None = None,
    ) -> list[Alerta]:
        consulta = select(Alerta)
        if menor_id is not None:
            consulta = consulta.where(Alerta.menor_id == menor_id)
        if tipo is not None:
            consulta = consulta.where(Alerta.tipo == tipo)
        if estado is not None:
            consulta = consulta.where(Alerta.estado == estado)
        return list(self.session.scalars(consulta.order_by(Alerta.created_at.desc())))

    def guardar(self, alerta: Alerta) -> Alerta:
        self.session.commit()
        return alerta


class AlertaDestinatarioRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, destinatario: AlertaDestinatario) -> AlertaDestinatario:
        self.session.add(destinatario)
        self.session.commit()
        return destinatario

    def listar_por_alerta(self, alerta_id: uuid.UUID) -> list[AlertaDestinatario]:
        consulta = select(AlertaDestinatario).where(AlertaDestinatario.alerta_id == alerta_id)
        return list(self.session.scalars(consulta))

    def por_alerta_y_usuario(self, alerta_id: uuid.UUID, usuario_id: uuid.UUID) -> AlertaDestinatario | None:
        consulta = select(AlertaDestinatario).where(
            AlertaDestinatario.alerta_id == alerta_id, AlertaDestinatario.usuario_id == usuario_id
        )
        return self.session.scalars(consulta).first()

    def listar_pendientes_de_usuario(self, usuario_id: uuid.UUID) -> list[AlertaDestinatario]:
        consulta = select(AlertaDestinatario).where(
            AlertaDestinatario.usuario_id == usuario_id, AlertaDestinatario.visto_en.is_(None)
        )
        return list(self.session.scalars(consulta))

    def listar_por_usuario(self, usuario_id: uuid.UUID) -> list[AlertaDestinatario]:
        consulta = select(AlertaDestinatario).where(AlertaDestinatario.usuario_id == usuario_id)
        return list(self.session.scalars(consulta))

    def guardar(self, destinatario: AlertaDestinatario) -> AlertaDestinatario:
        self.session.commit()
        return destinatario
