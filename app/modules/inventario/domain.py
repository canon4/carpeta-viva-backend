"""Inventario del Hogar: Entidades, objetos de valor y reglas de negocio.

Camas, muebles, personas que viven y red de apoyo. Ver docs/adr/0009-alertas-citas-inventario-alimentos.md
sección 3.
"""

TIPOS_INVENTARIO = ("cama", "mueble", "otro")
ESTADOS_INVENTARIO = ("bueno", "regular", "malo", "retirado")
ESTADOS_RECEPCION = ("bueno", "regular", "malo")

# ADR-0014, sección 2: fotos de evidencia de recepción. Mismos límites justificados ahí: formatos
# de celular comunes, tamaño suficiente para una foto de evidencia sin convertirse en otro módulo
# documental, máximo 6 por ítem.
MIME_FOTOS_PERMITIDOS = ("image/jpeg", "image/png", "image/webp")
FOTO_TAMANIO_MAXIMO_BYTES = 5 * 1024 * 1024
FOTOS_MAXIMO_POR_ITEM = 6
