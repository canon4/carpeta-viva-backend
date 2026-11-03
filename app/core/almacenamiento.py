"""Almacenamiento cifrado de archivos (ADR-0008, sección 1).

Módulo reutilizable: lo usa `documentos` hoy y, en el futuro, `madres.actualizar_mi_firma`
si se decide cifrar también la firma. Cifra con Fernet (clave única desde
`ARCHIVOS_CLAVE_MAESTRA`) y guarda cada versión en
`ARCHIVOS_DIR/{menor_id|hogar_id}/{documento_id}/{version}.enc`.

El hash SHA-256 se calcula sobre el contenido en claro (antes de cifrar), nunca sobre el
blob cifrado: sirve para auditar integridad real del contenido y detectar duplicados.
"""
import hashlib
import uuid
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


class ErrorIntegridadArchivo(Exception):
    """El contenido descifrado no coincide con el hash guardado."""


class RutaFueraDeArchivosDir(Exception):
    """`ruta` escaparía de `ARCHIVOS_DIR` (p. ej. `..`, ruta absoluta). Defensa en profundidad:
    hoy `ruta_relativa` siempre construye con UUID/int generados por el servidor (nunca con
    datos del usuario), pero `Reporte.referencia_archivo` (ADR-0008, fuera del alcance de este
    módulo) sí es provisto por el cliente y no pasa por `guardar()`. Si algún día se usa
    `leer()` sobre ese valor sin volver a validar, esta defensa evita que escape del directorio."""


def _fernet() -> Fernet:
    return Fernet(get_settings().archivos_clave_maestra)


def calcular_hash(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def ruta_relativa(propietario_id: uuid.UUID, documento_id: uuid.UUID, version: int) -> str:
    return f"{propietario_id}/{documento_id}/{version}.enc"


def _ruta_absoluta(ruta: str) -> Path:
    base = Path(get_settings().archivos_dir).resolve()
    absoluta = (base / ruta).resolve()
    try:
        absoluta.relative_to(base)
    except ValueError:
        raise RutaFueraDeArchivosDir(f"Ruta fuera de ARCHIVOS_DIR: {ruta!r}") from None
    return absoluta


def guardar(propietario_id: uuid.UUID, documento_id: uuid.UUID, version: int, contenido: bytes) -> tuple[str, str]:
    """Cifra `contenido` y lo escribe en disco. Devuelve (ruta_relativa, hash_sha256_en_claro)."""
    hash_sha256 = calcular_hash(contenido)
    relativa = ruta_relativa(propietario_id, documento_id, version)
    absoluta = _ruta_absoluta(relativa)
    absoluta.parent.mkdir(parents=True, exist_ok=True)
    token = _fernet().encrypt(contenido)
    absoluta.write_bytes(token)
    return relativa, hash_sha256


def leer(ruta: str, hash_sha256_esperado: str | None = None) -> bytes:
    """Descifra el archivo en `ruta` (relativa a `ARCHIVOS_DIR`). Si se da `hash_sha256_esperado`,
    recalcula el hash del contenido en claro y lo compara (verificación de integridad al leer)."""
    absoluta = _ruta_absoluta(ruta)
    token = absoluta.read_bytes()
    try:
        contenido = _fernet().decrypt(token)
    except InvalidToken as exc:
        raise ErrorIntegridadArchivo("No se pudo descifrar el archivo: clave inválida o contenido corrupto") from exc
    if hash_sha256_esperado is not None and calcular_hash(contenido) != hash_sha256_esperado:
        raise ErrorIntegridadArchivo("El hash del contenido descifrado no coincide con el registrado")
    return contenido
