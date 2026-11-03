"""Menores y Expedientes: Entidades, objetos de valor y reglas de negocio.

Carpeta digital de cada menor: datos personales, padres, historial médico y psicosocial, estado.
"""
from enum import Enum


class TipoDocumento(str, Enum):
    REGISTRO_CIVIL = "registro_civil"
    TARJETA_IDENTIDAD = "tarjeta_identidad"
    CEDULA = "cedula"
    PASAPORTE = "pasaporte"
    SIN_DOCUMENTO = "sin_documento"


class EstadoMenor(str, Enum):
    ACTIVO = "activo"
    EGRESADO = "egresado"
    EVADIDO = "evadido"
    FALLECIDO = "fallecido"


class Parentesco(str, Enum):
    PADRE = "padre"
    MADRE = "madre"
    OTRO = "otro"


class EstadoVital(str, Enum):
    VIVO = "vivo"
    FALLECIDO = "fallecido"
    DESCONOCIDO = "desconocido"


class SeccionSensible(str, Enum):
    FAMILIA = "familia"
    SALUD = "salud"
    PSICOSOCIAL = "psicosocial"


SECCIONES_SENSIBLES = {s.value for s in SeccionSensible}

CARGO_DEFENSOR = "defensor"

CAMPOS_TRACKEADOS = (
    "nombres",
    "apellidos",
    "fecha_nacimiento",
    "genero",
    "tipo_documento",
    "numero_documento",
    "estado_actual",
)


def requiere_snapshot(menor, datos) -> bool:
    """¿Alguno de los campos trackeados cambia? Si sí, hay que insertar snapshot en menores_history."""
    for campo in CAMPOS_TRACKEADOS:
        nuevo = getattr(datos, campo, None)
        if nuevo is not None and nuevo != getattr(menor, campo):
            return True
    return False


def cambios_trackeados(menor, cambios: dict) -> bool:
    """Igual que `requiere_snapshot`, pero sobre un diccionario de campo -> valor nuevo."""
    for campo in CAMPOS_TRACKEADOS:
        if campo not in cambios:
            continue
        nuevo = cambios[campo]
        if nuevo is not None and nuevo != getattr(menor, campo):
            return True
    return False
