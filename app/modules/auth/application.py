from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.config import get_settings
from app.core.errors import no_autenticado
from app.core.security import create_access_token, hash_password, verify_password

from .repository import UsuarioRepository

# Se verifica contra un hash falso cuando el usuario no existe, para igualar tiempos de respuesta.
_HASH_FALSO = hash_password("no-existe")


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(momento: datetime | None) -> datetime | None:
    """SQLite devuelve fechas sin zona; PostgreSQL con zona. Se normaliza a UTC."""
    if momento is None:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def _bloqueada() -> HTTPException:
    minutos = get_settings().login_bloqueo_minutos
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        f"Demasiados intentos fallidos. Intente de nuevo en {minutos} minutos.",
    )


def iniciar_sesion(session: Session, email: str, password: str, ip: str | None = None) -> str:
    settings = get_settings()
    email = email.strip().lower()
    repo = UsuarioRepository(session)
    usuario = repo.por_email(email)
    if usuario is None:
        verify_password(password, _HASH_FALSO)
        # No se guarda el texto escrito en el campo de correo: podría ser una contraseña tecleada
        # en el campo equivocado o un dato personal de un tercero.
        registrar_acceso(session, accion="login_fallido", ip=ip)
        raise no_autenticado()

    bloqueado_hasta = _utc(usuario.bloqueado_hasta)
    if bloqueado_hasta is not None and bloqueado_hasta > _ahora():
        registrar_acceso(session, accion="login_bloqueado", usuario_id=usuario.id, ip=ip)
        raise _bloqueada()

    if not usuario.activo or not verify_password(password, usuario.password_hash):
        usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
        if usuario.intentos_fallidos >= settings.login_max_intentos:
            usuario.bloqueado_hasta = _ahora() + timedelta(minutes=settings.login_bloqueo_minutos)
            usuario.intentos_fallidos = 0
            repo.guardar(usuario)
            registrar_acceso(session, accion="login_cuenta_bloqueada", usuario_id=usuario.id, ip=ip)
            raise _bloqueada()
        repo.guardar(usuario)
        registrar_acceso(session, accion="login_fallido", usuario_id=usuario.id, ip=ip)
        raise no_autenticado()

    if usuario.intentos_fallidos or usuario.bloqueado_hasta is not None:
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        repo.guardar(usuario)
    registrar_acceso(session, accion="login_ok", usuario_id=usuario.id, ip=ip)
    return create_access_token(str(usuario.id), usuario.rol)


def cambiar_contrasena(session: Session, usuario, actual: str, nueva: str, ip: str | None = None) -> str:
    """Cambia la contraseña propia (RF0.4). Invalida los tokens anteriores y devuelve uno nuevo."""
    settings = get_settings()
    if not verify_password(actual, usuario.password_hash):
        registrar_acceso(session, accion="contrasena_cambio_denegado", usuario_id=usuario.id, ip=ip)
        # 422 y no 401: un 401 haría que el frontend cierre la sesión por un error de tecleo.
        raise ValueError("La contraseña actual no es correcta")
    if len(nueva) < settings.password_longitud_minima:
        raise ValueError(f"La contraseña nueva debe tener al menos {settings.password_longitud_minima} caracteres")
    if nueva == actual:
        raise ValueError("La contraseña nueva debe ser distinta de la actual")
    if nueva.strip().lower() == usuario.email.lower():
        raise ValueError("La contraseña no puede ser igual al correo")
    usuario.password_hash = hash_password(nueva)
    # Precisión de segundos: el `iat` del JWT se guarda en segundos enteros.
    usuario.credenciales_cambiadas_en = _ahora().replace(microsecond=0)
    UsuarioRepository(session).guardar(usuario)
    registrar_acceso(session, accion="contrasena_cambiada", usuario_id=usuario.id, ip=ip)
    return create_access_token(str(usuario.id), usuario.rol)


def token_revocado(usuario, emitido_en: int | None) -> bool:
    """Un token emitido antes del último cambio de contraseña ya no vale."""
    cambio = _utc(usuario.credenciales_cambiadas_en)
    if cambio is None:
        return False
    if emitido_en is None:
        return True
    return datetime.fromtimestamp(emitido_en, timezone.utc) < cambio


def usuarios_por_rol(session: Session, rol: str, zona_id=None) -> list:
    """Wrapper público para otros módulos (p. ej. `alertas`, destinatarios de respaldo de
    evasión, ADR-0009) que necesitan resolver usuarios por rol sin tocar el repositorio ajeno."""
    return UsuarioRepository(session).listar_por_rol(rol, zona_id=zona_id)
