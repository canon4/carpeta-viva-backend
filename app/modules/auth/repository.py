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
