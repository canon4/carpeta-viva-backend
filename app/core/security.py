from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .config import get_settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(subject: str, rol: str) -> str:
    settings = get_settings()
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "rol": rol,
        "tipo": "access",
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    """Token de renovación (sección "esquema de sesión" de auth): solo viaja en una cookie
    httpOnly (nunca en el cuerpo JSON ni en el `Authorization`), por eso no lleva el rol ni se
    acepta en `usuario_actual` (defensa en profundidad si algún día se filtra por error)."""
    settings = get_settings()
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "tipo": "refresh",
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.jwt_refresh_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
