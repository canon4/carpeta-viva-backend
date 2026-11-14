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

# Respaldo histórico (ADR-0013, sección 7.1): estas dos constantes dejaron de ser la fuente de
# verdad de qué categorías existen. `configuracion.application.valor_valido_en_catalogo` contra
# los grupos "categoria_documento_menor"/"categoria_documento_hogar" es la validación vigente;
# admin puede agregar categorías nuevas sin tocar este archivo. Se dejan aquí como referencia de
# los valores migrados en la primera semilla, no se usan en la validación.
CATEGORIAS_MENOR = {
    "identidad", "salud", "psicosocial", "educacion", "familia_red_apoyo", "actas_traslados", "otros",
}
CATEGORIAS_HOGAR = {"madre_habilitacion", "otros"}

ESTADOS_FLUJO = ("borrador", "en_revision", "aprobado", "devuelto")

# Visor en pantalla (ADR-0011): solo tipos que el navegador puede mostrar de forma nativa, sin
# conversión en el servidor. Word/Excel y otros formatos se descargan para verlos, como ya hacían.
MIME_VISUALIZABLES = {"application/pdf", "image/jpeg", "image/png", "image/gif", "image/webp"}


def seccion_de_categoria(session, categoria: str) -> str | None:
    """Primero el respaldo fijo en código (categorías ya existentes); si la categoría no está
    ahí (creada por `admin` después de este ADR), consulta el catálogo administrable
    (ADR-0013, sección 5.1). `None`/básica solo como backstop defensivo, nunca como mecanismo
    principal para una categoría nueva sin mapear."""
    if categoria in SECCION_POR_CATEGORIA:
        return SECCION_POR_CATEGORIA[categoria]
    from app.modules.configuracion.application import seccion_acceso_de_opcion

    return seccion_acceso_de_opcion(session, "categoria_documento_menor", categoria)


def seccion_de_tipo_reporte(tipo_reporte: str) -> str | None:
    return SECCION_POR_TIPO_REPORTE.get(tipo_reporte)


def es_visualizable(mime_type: str) -> bool:
    return mime_type in MIME_VISUALIZABLES
