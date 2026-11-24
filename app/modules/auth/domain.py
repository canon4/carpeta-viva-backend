from enum import Enum


class Rol(str, Enum):
    MADRE = "madre"
    PROFESIONAL = "profesional"
    DEFENSOR = "defensor"
    COORDINADOR = "coordinador"
    AUDITOR = "auditor"
    ADMIN = "admin"


# Roles sin tabla propia de perfil (ADR-0019): su nombre vive en `Usuario.nombres`/`apellidos`.
# Madre y profesional/defensor ya tienen su nombre en su propia tabla y no pueden tocar estos
# campos para no crear una segunda fuente de verdad sobre la misma identidad.
ROLES_SIN_TABLA_PROPIA = (Rol.COORDINADOR.value, Rol.ADMIN.value, Rol.AUDITOR.value)

# Foto de perfil genérica (ADR-0019, sección 1): mismos límites que las fotos de evidencia de
# inventario (ADR-0014) — formatos de celular comunes, tamaño máximo 5 MB.
MIME_FOTOS_PERFIL_PERMITIDOS = ("image/jpeg", "image/png", "image/webp")
FOTO_PERFIL_TAMANIO_MAXIMO_BYTES = 5 * 1024 * 1024
