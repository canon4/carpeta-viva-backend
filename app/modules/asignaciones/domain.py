"""Asignaciones y Traslados: Entidades, objetos de valor y reglas de negocio.

Vincula al menor con el hogar con fecha de inicio y fin; actas de traslado.
"""
from enum import Enum


class TipoMovimiento(str, Enum):
    INGRESO = "ingreso"
    TRASLADO = "traslado"
    EGRESO = "egreso"


class EstadoAsignacion(str, Enum):
    VIGENTE = "vigente"
    CERRADA = "cerrada"
