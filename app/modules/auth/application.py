from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_autenticado
from app.core.security import create_access_token, hash_password, verify_password

from .repository import UsuarioRepository

# Se verifica contra un hash falso cuando el usuario no existe, para igualar tiempos de respuesta.
_HASH_FALSO = hash_password("no-existe")


def iniciar_sesion(session: Session, email: str, password: str, ip: str | None = None) -> str:
    email = email.strip().lower()
    usuario = UsuarioRepository(session).por_email(email)
    if usuario is None:
        verify_password(password, _HASH_FALSO)
    if usuario is None or not usuario.activo or not verify_password(password, usuario.password_hash):
        registrar_acceso(session, accion="login_fallido", recurso=email, ip=ip)
        raise no_autenticado()
    registrar_acceso(session, accion="login_ok", usuario_id=usuario.id, ip=ip)
    return create_access_token(str(usuario.id), usuario.rol)
