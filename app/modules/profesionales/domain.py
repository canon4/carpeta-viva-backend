"""Profesionales: Entidades, objetos de valor y reglas de negocio.

Datos del personal profesional (defensor, psicosocial, nutrición, trabajo social).
"""
from enum import Enum


class CargoProfesional(str, Enum):
    DEFENSOR = "defensor"
    PSICOSOCIAL = "psicosocial"
    NUTRICION = "nutricion"
    TRABAJO_SOCIAL = "trabajo_social"
