"""Asistente de IA: OCR local (ADR-0010, sección 1.1).

Corre siempre localmente, nunca contra un proveedor externo con el documento original (una
imagen con datos identificables de un NNA no puede seudonimizarse antes del OCR, porque el OCR
es precisamente el paso que produce el texto sobre el que luego se detectan los datos a
sustituir). Usa Tesseract (motor abierto, paquete de idioma `spa`) vía `pytesseract`.

Si el binario `tesseract` no está instalado en el sistema, se lanza `OcrNoDisponible` de forma
explícita (nunca falla en silencio ni bloquea el resto del módulo: la indexación en segundo
plano que use esta función debe capturarla y registrar `indexacion_pendiente`, sección 1.3).
"""
import io

MIME_IMAGENES = ("image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp", "image/webp")


class OcrNoDisponible(Exception):
    """El binario `tesseract` no está instalado o no se encuentra en PATH."""


def extraer_texto_imagen(contenido: bytes) -> str:
    """OCR de una imagen (foto de un documento, escaneo). Idioma español con reserva a inglés si
    el paquete `spa` no está instalado en el servidor (mejor texto parcial que ningún texto)."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depende de si las dependencias están instaladas
        raise OcrNoDisponible("pytesseract/Pillow no están instalados") from exc

    try:
        imagen = Image.open(io.BytesIO(contenido))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo leer la imagen: {exc}") from exc

    try:
        try:
            return pytesseract.image_to_string(imagen, lang="spa+eng")
        except pytesseract.TesseractError:
            # El paquete de idioma "spa" puede no estar instalado en este servidor; se
            # reintenta con el idioma por defecto antes de declarar el OCR no disponible.
            return pytesseract.image_to_string(imagen)
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrNoDisponible(
            "El binario 'tesseract' no está instalado en este servidor (pytesseract no lo encontró "
            "en PATH). Ver docs/adr/0010-asistente-ia-reportes-archivo-cierre.md sección 1.1."
        ) from exc


def extraer_texto(contenido: bytes, mime_type: str) -> str | None:
    """Punto de entrada único de extracción de texto para indexación (sección 1.2/1.3).

    - Imágenes: OCR local (puede lanzar `OcrNoDisponible`).
    - `text/plain`: texto ya nativo, sin OCR.
    - Cualquier otro tipo (PDF, Word, Excel): no se implementa extracción en esta fase (requiere
      librerías adicionales no instaladas, p. ej. `pypdf`/`python-docx`); se documenta como
      limitación conocida, no como falla silenciosa — devuelve `None` y quien llama decide si
      eso cuenta como "pendiente de indexar" o simplemente "sin texto indexable".
    """
    mime = (mime_type or "").lower()
    if mime in MIME_IMAGENES:
        return extraer_texto_imagen(contenido)
    if mime == "text/plain":
        return contenido.decode("utf-8", errors="replace")
    return None
