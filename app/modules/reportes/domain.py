"""Reportes: Entidades, objetos de valor y reglas de negocio (ADR-0010, sección 2).

Reportes generales, por zona, por menor y por madre: los cuatro niveles son consultas
agregadas de solo lectura, reusando la autorización por fila/sección ya construida en fases
anteriores (no se diseña un motor de permisos nuevo).
"""

NIVELES = ("general", "zona", "menor", "madre")
FORMATOS = ("json", "pdf", "csv")

SECCIONES_SENSIBLES = ("familia", "salud", "psicosocial")
