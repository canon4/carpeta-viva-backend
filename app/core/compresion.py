"""Compresión de imágenes para el historial de versiones (ADR-0011).

Cuando un documento se reemplaza por una versión nueva, la versión anterior deja de ser el
archivo vigente y solo sirve como registro histórico. Si es una imagen (fotos del celular,
papel digitalizado), se guarda una copia recomprimida en vez de la original para no acumular
espacio en disco con versiones que nadie vuelve a necesitar en calidad completa. PDF y otros
formatos se conservan tal cual: no hay una forma simple y confiable de recomprimirlos sin
librerías de sistema adicionales (fuera de alcance de este prototipo).
"""
from io import BytesIO

from PIL import Image, UnidentifiedImageError

DIMENSION_MAXIMA = 1280
CALIDAD_JPEG = 60


def comprimir_si_es_imagen(contenido: bytes, mime_type: str) -> tuple[bytes, str, bool]:
    """Si `contenido` es una imagen, devuelve (bytes_recomprimidos, "image/jpeg", True).
    Si no lo es, o no se puede procesar, devuelve (contenido, mime_type, False) sin fallar:
    conservar el original intacto es siempre preferible a perder un documento del expediente."""
    if not mime_type.startswith("image/"):
        return contenido, mime_type, False
    try:
        imagen = Image.open(BytesIO(contenido))
        imagen = imagen.convert("RGB")
        imagen.thumbnail((DIMENSION_MAXIMA, DIMENSION_MAXIMA))
        salida = BytesIO()
        imagen.save(salida, format="JPEG", quality=CALIDAD_JPEG, optimize=True)
        comprimido = salida.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        return contenido, mime_type, False
    if len(comprimido) >= len(contenido):
        return contenido, mime_type, False
    return comprimido, "image/jpeg", True
