"""Madres Sustitutas: Entidades, objetos de valor y reglas de negocio.

Datos de la madre sustituta: identificación, certificación y firma única.
"""
from enum import Enum


class EstadoCertificacion(str, Enum):
    PENDIENTE = "pendiente"
    VIGENTE = "vigente"
    VENCIDA = "vencida"
    SUSPENDIDA = "suspendida"
