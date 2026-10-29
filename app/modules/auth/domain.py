from enum import Enum


class Rol(str, Enum):
    MADRE = "madre"
    PROFESIONAL = "profesional"
    DEFENSOR = "defensor"
    COORDINADOR = "coordinador"
    AUDITOR = "auditor"
    ADMIN = "admin"
