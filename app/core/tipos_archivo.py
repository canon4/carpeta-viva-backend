"""Detección del tipo real de un archivo por su contenido (firma de bytes).

El tipo que declara el cliente (`Content-Type` del multipart) no es confiable: se puede subir un
ejecutable declarado como `image/jpeg`. Aquí se decide el tipo mirando los bytes y, para formatos
contenedores (ZIP de Office, OLE de Office antiguo), la extensión del nombre. El tipo detectado es
el que se guarda; el declarado se ignora.

Sin dependencias nuevas (no `python-magic`/libmagic, que en Windows exige binarios aparte).
"""
import io
import zipfile

# Tipos de documento aceptados en Gestión Documental (RF2: papel digitalizado, PDF, Word/Excel,
# fotos del celular y texto). Cualquier otro contenido se rechaza.
MIME_PDF = "application/pdf"
MIME_JPEG = "image/jpeg"
MIME_PNG = "image/png"
MIME_GIF = "image/gif"
MIME_WEBP = "image/webp"
MIME_HEIC = "image/heic"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
MIME_DOC = "application/msword"
MIME_XLS = "application/vnd.ms-excel"
MIME_TEXTO = "text/plain"
MIME_CSV = "text/csv"

IMAGENES = (MIME_JPEG, MIME_PNG, MIME_GIF, MIME_WEBP, MIME_HEIC)

_OOXML_POR_CARPETA = {"word/": MIME_DOCX, "xl/": MIME_XLSX, "ppt/": MIME_PPTX}
_OLE_POR_EXTENSION = {".doc": MIME_DOC, ".xls": MIME_XLS}
_FIRMAS_PROHIBIDAS = (b"MZ", b"\x7fELF", b"#!", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa")


class TipoArchivoNoPermitido(ValueError):
    pass


def _extension(nombre: str) -> str:
    nombre = (nombre or "").lower()
    return nombre[nombre.rfind("."):] if "." in nombre else ""


def _ooxml(contenido: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            nombres = z.namelist()
    except (zipfile.BadZipFile, ValueError):
        return None
    if "[Content_Types].xml" not in nombres:
        return None
    for carpeta, mime in _OOXML_POR_CARPETA.items():
        if any(n.startswith(carpeta) for n in nombres):
            # Documentos con macros (vbaProject.bin) no se aceptan.
            if any(n.endswith("vbaProject.bin") for n in nombres):
                return None
            return mime
    return None


def _es_texto(contenido: bytes) -> bool:
    if b"\x00" in contenido[:8192]:
        return False
    try:
        contenido.decode("utf-8")
    except UnicodeDecodeError:
        try:
            contenido.decode("latin-1")
        except UnicodeDecodeError:  # pragma: no cover - latin-1 decodifica todo
            return False
        # latin-1 decodifica cualquier byte: exigir mayoría de caracteres imprimibles.
        imprimibles = sum(1 for b in contenido[:8192] if b >= 32 or b in (9, 10, 13))
        return imprimibles / max(1, min(len(contenido), 8192)) > 0.95
    return True


def detectar_tipo(contenido: bytes, nombre: str = "") -> str | None:
    """Tipo MIME real según los bytes, o None si no es un formato aceptado."""
    if not contenido:
        return None
    if contenido.startswith(_FIRMAS_PROHIBIDAS):
        return None
    if contenido.startswith(b"%PDF-"):
        return MIME_PDF
    if contenido.startswith(b"\xff\xd8\xff"):
        return MIME_JPEG
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return MIME_PNG
    if contenido.startswith((b"GIF87a", b"GIF89a")):
        return MIME_GIF
    if contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        return MIME_WEBP
    if contenido[4:8] == b"ftyp" and contenido[8:12] in (b"heic", b"heix", b"mif1", b"msf1", b"hevc"):
        return MIME_HEIC
    if contenido.startswith(b"PK\x03\x04"):
        return _ooxml(contenido)
    if contenido.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return _OLE_POR_EXTENSION.get(_extension(nombre))
    if _es_texto(contenido):
        # HTML, Markdown, JSON y similares se guardan como texto plano: nunca se sirven como HTML.
        return MIME_CSV if _extension(nombre) == ".csv" else MIME_TEXTO
    return None


def validar_documento(contenido: bytes, nombre: str = "") -> str:
    """El tamaño máximo ya lo controla `documentos` con `archivos_tamanio_maximo_bytes`."""
    tipo = detectar_tipo(contenido, nombre)
    if tipo is None:
        raise TipoArchivoNoPermitido(
            "Tipo de archivo no permitido: use PDF, imagen (JPEG, PNG, GIF, WEBP, HEIC), "
            "Word, Excel, PowerPoint sin macros o texto"
        )
    return tipo


def validar_imagen(contenido: bytes, permitidos: tuple[str, ...]) -> str:
    tipo = detectar_tipo(contenido)
    if tipo not in permitidos:
        raise TipoArchivoNoPermitido("El archivo no es una imagen permitida")
    return tipo
