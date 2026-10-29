import uuid

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.modules.auth.domain import Rol
from app.modules.auth.models import Usuario
from app.modules.auth.repository import UsuarioRepository

from .database import get_session
from .errors import no_autenticado, prohibido
from .security import decode_token

_bearer = HTTPBearer(auto_error=False)


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> Usuario:
    if credenciales is None:
        raise no_autenticado("Falta el token")
    try:
        datos = decode_token(credenciales.credentials)
        usuario_id = uuid.UUID(datos["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise no_autenticado("Token inválido o vencido")
    usuario = UsuarioRepository(session).por_id(usuario_id)
    if usuario is None or not usuario.activo:
        raise no_autenticado("Usuario inactivo o inexistente")
    return usuario


def requiere_roles(*roles: Rol):
    permitidos = {r.value for r in roles}

    def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in permitidos:
            raise prohibido()
        return usuario

    return verificar
