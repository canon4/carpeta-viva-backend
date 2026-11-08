"""Asistente de IA: clasificación de categoría al cargar un documento (ADR-0010, sección 1.2).

Comparación por similitud de coseno contra un pequeño conjunto de ejemplos de referencia por
categoría (datos sintéticos, versionados aquí mismo), no un clasificador entrenado. Devuelve
`categoria_sugerida` + `confianza`; la madre/profesional confirma o corrige antes de guardar —
la IA nunca fija la categoría por sí sola (ADR-0002 punto 6).
"""
from .domain import similitud_coseno
from .embeddings import calcular_embeddings

# 3-5 fragmentos representativos por categoría (`documentos.domain.CATEGORIAS`), datos
# sintéticos, en español, suficientes para un vecino más cercano simple.
EJEMPLOS_REFERENCIA_CATEGORIA: dict[str, list[str]] = {
    "identidad": [
        "Registro civil de nacimiento del menor, expedido por la Registraduría Nacional.",
        "Fotocopia de la tarjeta de identidad del niño, niña o adolescente.",
        "Copia de la cédula de ciudadanía del adolescente al cumplir la mayoría de edad.",
    ],
    "salud": [
        "Historia clínica con diagnóstico, tratamiento y controles médicos del menor.",
        "Carné de vacunación y esquema de inmunización al día.",
        "Informe de valoración nutricional y crecimiento del niño.",
        "Resultado de examen médico general y remisión a especialista.",
    ],
    "psicosocial": [
        "Informe psicosocial de seguimiento con observaciones de comportamiento y adaptación.",
        "Valoración psicológica inicial del menor al ingresar al hogar sustituto.",
        "Informe de trabajo social sobre la dinámica familiar y el entorno del niño.",
    ],
    "educacion": [
        "Certificado de matrícula escolar del año en curso.",
        "Boletín de calificaciones del colegio del menor.",
        "Constancia de estudios expedida por la institución educativa.",
    ],
    "familia_red_apoyo": [
        "Información sobre la madre biológica, su dirección y estado actual.",
        "Datos de contacto de la familia extensa y red de apoyo del menor.",
        "Informe de visita domiciliaria a la familia biológica del niño.",
    ],
    "actas_traslados": [
        "Acta de traslado del menor de un hogar sustituto a otro.",
        "Acta de ingreso del niño al hogar sustituto, firmada por la madre sustituta.",
        "Resolución administrativa del defensor de familia sobre la ubicación del menor.",
    ],
    "madre_habilitacion": [
        "Certificado de habilitación de la madre sustituta expedido por el operador.",
        "Documento de afiliación de la madre sustituta a la fundación.",
    ],
    "otros": [
        "Documento administrativo general sin categoría específica asignada.",
        "Comunicación interna del operador sobre el hogar sustituto.",
    ],
}


def _vectores_referencia() -> dict[str, list[list[float]]]:
    """Calculados perezosamente (requieren el modelo de embeddings); no se cachean entre
    llamadas aquí porque `embeddings.calcular_embeddings` ya memoiza la carga del modelo
    (costoso es cargar el modelo, no calcular un puñado de vectores de referencia)."""
    vectores: dict[str, list[list[float]]] = {}
    for categoria, ejemplos in EJEMPLOS_REFERENCIA_CATEGORIA.items():
        vectores[categoria] = calcular_embeddings(ejemplos)
    return vectores


def clasificar_categoria(texto: str) -> tuple[str | None, float]:
    """Devuelve `(categoria_sugerida, confianza)` por vecino más cercano sobre los ejemplos de
    referencia. `confianza` es la similitud de coseno máxima encontrada (0 a 1). Si `texto` está
    vacío, no hay nada que clasificar: devuelve `(None, 0.0)`."""
    texto = (texto or "").strip()
    if not texto:
        return None, 0.0

    vector_texto = calcular_embeddings([texto])[0]
    referencias = _vectores_referencia()

    mejor_categoria: str | None = None
    mejor_similitud = -1.0
    for categoria, vectores in referencias.items():
        for vector in vectores:
            similitud = similitud_coseno(vector_texto, vector)
            if similitud > mejor_similitud:
                mejor_similitud = similitud
                mejor_categoria = categoria

    return mejor_categoria, max(mejor_similitud, 0.0)
