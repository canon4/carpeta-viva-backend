"""Inventario del Hogar: Entidades, objetos de valor y reglas de negocio.

Camas, muebles, personas que viven y red de apoyo. Ver docs/adr/0009-alertas-citas-inventario-alimentos.md
sección 3.
"""

TIPOS_INVENTARIO = ("cama", "mueble", "otro")
ESTADOS_INVENTARIO = ("bueno", "regular", "malo", "retirado")
