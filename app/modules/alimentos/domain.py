"""Control de Alimentos: Entidades, objetos de valor y reglas de negocio.

Ingreso de cada mercado, si es perecedero y su fecha de vencimiento. `fecha_vencimiento` solo
tiene sentido si `perecedero=true`; se valida aquí y no en constraint SQL (ADR-0009, sección 4).
"""
from datetime import date


def validar_perecedero(perecedero: bool, fecha_vencimiento: date | None) -> None:
    if not perecedero and fecha_vencimiento is not None:
        raise ValueError("fecha_vencimiento solo aplica si el alimento es perecedero")


def esta_vencido(perecedero: bool, fecha_vencimiento: date | None, consumido: bool, hoy: date) -> bool:
    if consumido or not perecedero or fecha_vencimiento is None:
        return False
    return fecha_vencimiento < hoy
