"""Zonas y Hogares: Entidades, objetos de valor y reglas de negocio.

Organiza los hogares sustitutos por zona y guarda los datos de cada hogar.
"""
from enum import Enum


class EstadoHogar(str, Enum):
    ACTIVO = "activo"
    INACTIVO = "inactivo"
    SUSPENDIDO = "suspendido"


CAPACIDAD_MAXIMA_NORMATIVA = 13  # Res. ICBF; en la práctica se opera con 5-6 por hacinamiento.


def validar_capacidad(capacidad: int) -> None:
    """La capacidad debe ser positiva y no superar el máximo normativo."""
    if capacidad < 1 or capacidad > CAPACIDAD_MAXIMA_NORMATIVA:
        raise ValueError(f"La capacidad debe estar entre 1 y {CAPACIDAD_MAXIMA_NORMATIVA}")
