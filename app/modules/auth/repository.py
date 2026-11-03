import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Usuario


class UsuarioRepository:
    def __init__(self, session: Session):
        self.session = session

    def por_email(self, email: str) -> Usuario | None:
        return self.session.scalar(select(Usuario).where(Usuario.email == email))

    def por_id(self, usuario_id: uuid.UUID) -> Usuario | None:
        return self.session.get(Usuario, usuario_id)

    def listar_por_rol(self, rol: str, zona_id: uuid.UUID | None = None) -> list[Usuario]:
        """Usado por `alertas` (ADR-0009) para resolver destinatarios de respaldo: coordinador de
        una zona o, en su defecto, cualquier admin."""
        consulta = select(Usuario).where(Usuario.rol == rol, Usuario.activo.is_(True))
        if zona_id is not None:
            consulta = consulta.where(Usuario.zona_id == zona_id)
        return list(self.session.scalars(consulta))
