"""Gestión Documental: Entidades, objetos de valor y reglas de negocio.

Carga, clasificación, versionado y flujo de revisión: la madre crea, el profesional aprueba.
Ver docs/adr/0008-gestion-documental-almacenamiento-cifrado-y-flujo.md.
"""

# Mapeo categoria -> sección de permiso (ADR-0007/ADR-0008 sección 2). `None` significa
# visibilidad básica (puede_ver_menor), no sección sensible.
SECCION_POR_CATEGORIA: dict[str, str | None] = {
    "identidad": None,
    "salud": "salud",
    "psicosocial": "psicosocial",
    "educacion": None,
    "familia_red_apoyo": "familia",
    "actas_traslados": None,
    "madre_habilitacion": None,  # documento de hogar, autorización propia (sección 2.1)
    "otros": None,
}

# Mapeo tipo_reporte -> sección, mismo criterio salud/psicosocial (ADR-0008, sección 4).
SECCION_POR_TIPO_REPORTE: dict[str, str | None] = {
    "informe_medico": "salud",
    "informe_psicosocial": "psicosocial",
    "informe_nutricion": "salud",
    "informe_trabajo_social": "familia",
    "seguimiento": None,
}

CATEGORIAS_MENOR = {
    "identidad", "salud", "psicosocial", "educacion", "familia_red_apoyo", "actas_traslados", "otros",
}
CATEGORIAS_HOGAR = {"madre_habilitacion", "otros"}

ESTADOS_FLUJO = ("borrador", "en_revision", "aprobado", "devuelto")

# Visor en pantalla (ADR-0011): solo tipos que el navegador puede mostrar de forma nativa, sin
# conversión en el servidor. Word/Excel y otros formatos se descargan para verlos, como ya hacían.
MIME_VISUALIZABLES = {"application/pdf", "image/jpeg", "image/png", "image/gif", "image/webp"}


def seccion_de_categoria(categoria: str) -> str | None:
    return SECCION_POR_CATEGORIA.get(categoria)


def seccion_de_tipo_reporte(tipo_reporte: str) -> str | None:
    return SECCION_POR_TIPO_REPORTE.get(tipo_reporte)


def es_visualizable(mime_type: str) -> bool:
    return mime_type in MIME_VISUALIZABLES
