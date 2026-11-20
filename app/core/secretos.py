"""Cifrado de secretos pequeños guardados en la base (por ejemplo, la clave de API del asistente).

Usa la misma clave maestra Fernet que protege los archivos (`ARCHIVOS_CLAVE_MAESTRA`, ADR-0008):
quien obtiene una copia de la base sin esa clave no puede leer el secreto. El texto en claro
nunca se registra ni se devuelve por la API; solo se usa en memoria para llamar al proveedor.
"""
from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


class SecretoIlegible(Exception):
    """El secreto no se pudo descifrar (la clave maestra cambió o el dato está corrupto)."""


def _fernet() -> Fernet:
    return Fernet(get_settings().archivos_clave_maestra)


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode("utf-8")).decode("ascii")


def descifrar(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretoIlegible("No se pudo descifrar el secreto guardado") from exc
