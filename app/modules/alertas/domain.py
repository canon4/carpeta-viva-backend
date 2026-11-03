"""Alertas y Evasiones: constantes y reglas de dominio (ADR-0009, sección 1)."""

TIPOS_ALERTA = ("evasion", "visita_vencida", "documento_faltante")
ORIGENES_ALERTA = ("manual", "automatica")
ESTADOS_ALERTA = ("activa", "cerrada")

# Roles de profesional que deben enterarse de una evasión (CLAUDE.md: "la alerta llega... al
# defensor y a la profesional psicosocial asignados").
ROLES_DESTINATARIOS_EVASION = ("defensor", "psicosocial")
