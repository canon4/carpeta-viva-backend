"""Citas y Recordatorios: constantes y reglas de dominio (ADR-0009, sección 2).

Corrección de seguridad incorporada: `notas` es texto libre sin control de contenido, así que se
filtra con `tiene_permiso_seccion` según el tipo de cita; el resto de la fila (tipo, fecha, lugar,
estado) es visible con `puede_ver_menor`, sin filtro (son metadatos de agenda).
"""

TIPOS_CITA = ("medica", "psicosocial", "reunion_familia", "otro")
ESTADOS_CITA = ("pendiente", "cumplida", "no_asistio")

SECCION_POR_TIPO_CITA: dict[str, str | None] = {
    "medica": "salud",
    "psicosocial": "psicosocial",
    "reunion_familia": "familia",
    "otro": None,
}


def seccion_de_tipo_cita(tipo: str) -> str | None:
    return SECCION_POR_TIPO_CITA.get(tipo)
