"""Asistente de IA: embeddings locales (ADR-0010, sección 1.3).

Modelo `sentence-transformers` multilingüe (`intfloat/multilingual-e5-small` por defecto,
384 dimensiones), ejecutado en CPU dentro del propio proceso del backend. El texto nunca sale
del sistema para este paso: a diferencia del LLM de generación (`app/core/ia_llm.py`), aquí no
hay proveedor externo que intercambiar, solo el nombre del modelo local por configuración
(`IA_EMBEDDINGS_MODELO`).

El modelo se carga una sola vez por proceso (`lru_cache`): la primera llamada puede tardar
(descarga desde Hugging Face Hub si no está en caché local, más el tiempo de carga de pesos);
las siguientes reutilizan la instancia ya cargada en memoria.
"""
from functools import lru_cache

from app.core.config import get_settings


class EmbeddingsNoDisponibles(Exception):
    """El modelo de embeddings no se pudo cargar (sin red para descargarlo la primera vez, sin
    espacio en disco, dependencia no instalada, etc.). La capa de aplicación debe capturar esta
    excepción y no bloquear el resto del sistema por esto (ADR-0010, sección 1.3: la indexación
    es una tarea en segundo plano que puede fallar y reintentarse)."""


@lru_cache
def _modelo():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - depende de si la dependencia está instalada
        raise EmbeddingsNoDisponibles(
            "sentence-transformers no está instalado; agréguelo a requirements.txt e instálelo"
        ) from exc
    nombre = get_settings().ia_embeddings_modelo
    try:
        return SentenceTransformer(nombre)
    except Exception as exc:  # noqa: BLE001 - cualquier falla de red/disco al descargar el modelo
        raise EmbeddingsNoDisponibles(f"No se pudo cargar el modelo de embeddings {nombre!r}: {exc}") from exc


def identificador_modelo() -> str:
    """`modelo_embedding` guardado en `fragmentos_documento` (sección 1.4): nombre + versión,
    para poder reindexar todo sin ambigüedad si cambia el modelo (`IA_EMBEDDINGS_VERSION`)."""
    settings = get_settings()
    return f"{settings.ia_embeddings_modelo}@{settings.ia_embeddings_version}"


def calcular_embedding(texto: str) -> list[float]:
    """Embedding de un solo texto (p. ej. la pregunta del usuario en el flujo RAG)."""
    return calcular_embeddings([texto])[0]


def calcular_embeddings(textos: list[str]) -> list[list[float]]:
    """Embeddings en lote (p. ej. los fragmentos de un documento al indexarlo). `e5-small`
    recomienda prefijar `"query: "`/`"passage: "` según el uso; para este prototipo (búsqueda
    simétrica pregunta/fragmento) se usa un único prefijo `"query: "` en ambos casos, suficiente
    para la tarea de similitud que necesitamos aquí."""
    if not textos:
        return []
    modelo = _modelo()
    vectores = modelo.encode([f"query: {t}" for t in textos], normalize_embeddings=True)
    return [v.tolist() for v in vectores]
