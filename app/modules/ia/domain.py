"""Asistente de IA: Entidades, objetos de valor y reglas de negocio puras (sin acceso a BD).

Busca, resume y clasifica con citas; consulta solo por la capa de aplicación (ADR-0002/0003).
Aquí viven las reglas que no dependen de una sesión de base de datos: partir texto en
fragmentos, los patrones de seudonimización por regex y el formato de las citas.
"""
import math
import re
import unicodedata

TAMANO_FRAGMENTO_PALABRAS = 120  # ~500-800 tokens aproximados por fragmento (sección 1.4)


def similitud_coseno(a: list[float], b: list[float]) -> float:
    """Compartida por `clasificacion.py` (vecino más cercano) y `application.py` (ranking de
    fragmentos en el flujo RAG): se calcula en Python sobre los vectores ya filtrados por
    permiso, no con el operador `<=>` de pgvector directamente — para el volumen de un
    prototipo (decenas de fragmentos por menor) es equivalente y portable entre PostgreSQL y
    SQLite (usado en pruebas); con mayor volumen conviene empujar el `order_by` al índice HNSW."""
    producto = sum(x * y for x, y in zip(a, b))
    norma_a = math.sqrt(sum(x * x for x in a))
    norma_b = math.sqrt(sum(y * y for y in b))
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return producto / (norma_a * norma_b)


def partir_en_fragmentos(texto: str, tamano_palabras: int = TAMANO_FRAGMENTO_PALABRAS) -> list[str]:
    """Divide un texto largo en fragmentos de tamaño aproximado, por palabras (simple y
    determinístico; suficiente para el volumen del prototipo, sin tokenizador de más)."""
    palabras = texto.split()
    if not palabras:
        return []
    fragmentos = []
    for inicio in range(0, len(palabras), tamano_palabras):
        fragmento = " ".join(palabras[inicio : inicio + tamano_palabras]).strip()
        if fragmento:
            fragmentos.append(fragmento)
    return fragmentos


def normalizar_nombre(nombre: str) -> str:
    """Mayúsculas sin acentos, espacios colapsados: para comparar nombres por coincidencia
    exacta sin que una tilde o el uso de mayúsculas distintas rompa la sustitución (corrección
    de seguridad, ADR-0010 sección 1.4, punto 5)."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", nombre) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_acentos).strip().upper()


# ---------------------------------------------------------------------------
# Seudonimización por patrón (datos sueltos sin fila en el sistema, sección 1.4)
# ---------------------------------------------------------------------------
# NOTA DE ALCANCE (obligatoria, ADR-0010 revisión de seguridad punto 5): estos patrones más la
# sustitución por nombre conocido (seudonimizacion.py) cubren entidades ya modeladas en el
# sistema y datos estructurados sueltos (teléfono, documento, correo, fecha). Un tercero
# mencionado en texto libre que NO tiene fila en el sistema (p. ej. "la vecina Rosa dijo...")
# NO se detecta con esto — requiere NER de personas (spaCy es_core_news), no implementado aquí.
# Este mecanismo es, por tanto, BLOQUEANTE para activar `anonimizado=false` (datos reales) hasta
# que se agregue esa pasada de NER; no bloquea el uso con datos sintéticos (decisión de Diego,
# sección 1.6). Ver `GET /ia/estado` -> `seudonimizacion_cobertura`.
SEUDONIMIZACION_COBERTURA = (
    "entidades_conocidas (menor/familiares/madre/profesionales, todo el sistema) + regex "
    "(teléfono/documento/correo/fecha) — sin NER de terceros sin fila en el sistema; "
    "no usar con datos reales (anonimizado=false) sin agregar NER antes"
)

_PATRONES_REGEX: list[tuple[str, re.Pattern]] = [
    ("CORREO", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("TELEFONO", re.compile(r"(?:\+?57)?[\s-]?3\d{9}\b|(?:\+?57)?[\s-]?\(?\d{1,3}\)?[\s-]?\d{3}[\s-]?\d{4}\b")),
    ("FECHA", re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")),
    ("DOCUMENTO", re.compile(r"\b\d{6,12}\b")),
]


def seudonimizar_por_patron(texto: str) -> tuple[str, dict[str, str]]:
    """Reemplaza teléfonos/documentos/correos/fechas sueltos por marcadores `[TIPO_n]`. Devuelve
    el texto sustituido y el mapa `marcador -> valor original` (solo en memoria, para restituir
    al final de la misma solicitud, sección 1.4: "no se crea una tabla de pseudónimos")."""
    mapa: dict[str, str] = {}
    contador: dict[str, int] = {}

    def _reemplazar(etiqueta: str):
        def _sub(match: re.Match) -> str:
            contador[etiqueta] = contador.get(etiqueta, 0) + 1
            marcador = f"[{etiqueta}_{contador[etiqueta]}]"
            mapa[marcador] = match.group(0)
            return marcador

        return _sub

    resultado = texto
    for etiqueta, patron in _PATRONES_REGEX:
        resultado = patron.sub(_reemplazar(etiqueta), resultado)
    return resultado, mapa


def restituir(texto: str, *mapas: dict[str, str]) -> str:
    """Reemplaza cada marcador por su valor/nombre real. El orden de aplicación no importa:
    los marcadores son únicos entre sí (prefijos distintos por tipo de entidad/patrón)."""
    resultado = texto
    for mapa in mapas:
        for marcador, real in mapa.items():
            resultado = resultado.replace(marcador, real)
    return resultado


def formatear_cita(*, categoria: str, fecha: str, documento_id: str, version: int) -> str:
    """Las citas nunca usan nombres reales (sección 1.5, paso 6): categoría, fecha, id y
    versión del documento/reporte alcanzan para que el usuario (que ya tiene permiso) ubique
    la fuente exacta."""
    return f"[{categoria}, {fecha}, documento {documento_id} v{version}]"
