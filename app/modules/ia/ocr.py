"""Asistente de IA: extracción de texto para indexar (ADR-0010, sección 1.1/1.2).

Corre siempre localmente, nunca contra un proveedor externo con el documento original (una
imagen con datos identificables de un NNA no puede seudonimizarse antes del OCR, porque el OCR
es precisamente el paso que produce el texto sobre el que luego se detectan los datos a
sustituir). Las imágenes usan Tesseract (motor abierto, paquete de idioma `spa`) vía
`pytesseract`; PDF, Word (.docx) y Excel (.xlsx) extraen su texto nativo (sin OCR) con
`pypdf`/`python-docx`/`openpyxl`, sin binarios de sistema adicionales.

Si falta una dependencia o un binario (`tesseract`), se lanza `OcrNoDisponible` de forma
explícita (nunca falla en silencio ni bloquea el resto del módulo: la indexación en segundo
plano que use esta función debe capturarla y registrar `indexacion_pendiente`, sección 1.3).
"""
import io

MIME_IMAGENES = ("image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp", "image/webp")
MIME_PDF = "application/pdf"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_TEXTO_PLANO = ("text/plain", "text/csv")


class OcrNoDisponible(Exception):
    """Falta una dependencia de extracción, o el binario `tesseract` no está instalado/en PATH."""


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


def extraer_texto_pdf(contenido: bytes) -> str:
    """Texto nativo de un PDF (capa de texto real, p. ej. generado digitalmente). `pypdf` no hace
    OCR: un PDF que sea solo páginas escaneadas (imagen pura, sin capa de texto) sigue sin
    indexarse, igual que una foto sin Tesseract instalado — limitación conocida, no falla
    silenciosa (devuelve texto vacío, que `indexar_fragmentos` trata como "sin texto")."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depende de si la dependencia está instalada
        raise OcrNoDisponible("pypdf no está instalado") from exc

    try:
        lector = PdfReader(io.BytesIO(contenido))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo leer el PDF: {exc}") from exc

    return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)


def extraer_texto_docx(contenido: bytes) -> str:
    """Texto de un documento Word (.docx): párrafos y celdas de tabla, en orden."""
    try:
        import docx
    except ImportError as exc:  # pragma: no cover - depende de si la dependencia está instalada
        raise OcrNoDisponible("python-docx no está instalado") from exc

    try:
        documento = docx.Document(io.BytesIO(contenido))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo leer el documento Word: {exc}") from exc

    partes = [p.text for p in documento.paragraphs if p.text]
    for tabla in documento.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                if celda.text:
                    partes.append(celda.text)
    return "\n".join(partes)


def extraer_texto_xlsx(contenido: bytes) -> str:
    """Texto de un libro Excel (.xlsx): valores de celda de todas las hojas, fila por fila
    (fórmulas evaluadas con su último valor calculado, `data_only=True`)."""
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - depende de si la dependencia está instalada
        raise OcrNoDisponible("openpyxl no está instalado") from exc

    try:
        libro = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo leer el Excel: {exc}") from exc

    partes = []
    for hoja in libro.worksheets:
        for fila in hoja.iter_rows(values_only=True):
            valores = [str(v) for v in fila if v is not None]
            if valores:
                partes.append(" ".join(valores))
    return "\n".join(partes)


def extraer_texto(contenido: bytes, mime_type: str) -> str | None:
    """Punto de entrada único de extracción de texto para indexación (sección 1.2/1.3).

    - Imágenes: OCR local (puede lanzar `OcrNoDisponible`).
    - `text/plain`/`text/csv`: texto ya nativo, sin procesar.
    - PDF/Word (.docx)/Excel (.xlsx): texto nativo del formato (sin OCR; puede lanzar
      `OcrNoDisponible` si falta la librería).
    - Cualquier otro tipo (PowerPoint, Word/Excel antiguos `.doc`/`.xls`): no se implementa
      extracción en esta fase (requieren librerías/parseo adicionales); se documenta como
      limitación conocida, no como falla silenciosa — devuelve `None` y quien llama decide si
      eso cuenta como "pendiente de indexar" o simplemente "sin texto indexable".
    """
    mime = (mime_type or "").lower()
    if mime in MIME_IMAGENES:
        return extraer_texto_imagen(contenido)
    if mime in MIME_TEXTO_PLANO:
        return contenido.decode("utf-8", errors="replace")
    if mime == MIME_PDF:
        return extraer_texto_pdf(contenido)
    if mime == MIME_DOCX:
        return extraer_texto_docx(contenido)
    if mime == MIME_XLSX:
        return extraer_texto_xlsx(contenido)
    return None
