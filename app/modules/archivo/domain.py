"""Archivo y Cierre: Entidades, objetos de valor y reglas de negocio (ADR-0010, sección 3).

Archiva el expediente al cierre del caso y lo exporta al destino por definir (provisional:
almacenamiento local cifrado, sección 3.4).
"""

# ADR-0010, sección 3.1: "evadido" no dispara archivo (el caso sigue abierto, se busca al NNA).
ESTADOS_QUE_DISPARAN_ARCHIVO = ("egresado", "fallecido")


def condicion_archivo_cumplida(estado_actual: str, hay_asignacion_vigente: bool) -> bool:
    """ADR-0010, sección 3.1: el archivo se habilita cuando el menor está egresado/fallecido
    y no tiene ninguna asignación vigente (el caso está realmente cerrado, no es un traslado)."""
    return estado_actual in ESTADOS_QUE_DISPARAN_ARCHIVO and not hay_asignacion_vigente
