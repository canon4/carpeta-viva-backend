"""Profesionales: Casos de uso.

Datos del personal profesional (defensor, psicosocial, nutrición, trabajo social).
"""
import uuid

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado

from .models import MenorProfesional, Profesional
from .repository import MenorProfesionalRepository, ProfesionalRepository
from .schemas import ProfesionalCreate, ProfesionalUpdate


def crear_profesional(session: Session, datos: ProfesionalCreate, usuario_id: uuid.UUID) -> Profesional:
    profesional = Profesional(
        usuario_id=datos.usuario_id,
        nombres=datos.nombres,
        apellidos=datos.apellidos,
        cargo=datos.cargo,
        especialidad=datos.especialidad,
        numero_registro=datos.numero_registro,
    )
    profesional = ProfesionalRepository(session).crear(profesional)
    registrar_acceso(session, accion="profesional_creado", usuario_id=usuario_id, recurso=str(profesional.id))
    return profesional


def listar_profesionales(session: Session, cargo: str | None = None) -> list[Profesional]:
    return ProfesionalRepository(session).listar(cargo)


def obtener_profesional(session: Session, profesional_id: uuid.UUID) -> Profesional:
    profesional = ProfesionalRepository(session).por_id(profesional_id)
    if profesional is None:
        raise no_encontrado("Profesional no encontrado")
    return profesional


def actualizar_profesional(
    session: Session, profesional_id: uuid.UUID, datos: ProfesionalUpdate, usuario_id: uuid.UUID
) -> Profesional:
    profesional = obtener_profesional(session, profesional_id)
    if datos.nombres is not None:
        profesional.nombres = datos.nombres
    if datos.apellidos is not None:
        profesional.apellidos = datos.apellidos
    if datos.cargo is not None:
        profesional.cargo = datos.cargo
    if datos.especialidad is not None:
        profesional.especialidad = datos.especialidad
    if datos.numero_registro is not None:
        profesional.numero_registro = datos.numero_registro
    profesional = ProfesionalRepository(session).guardar(profesional)
    registrar_acceso(session, accion="profesional_actualizado", usuario_id=usuario_id, recurso=str(profesional.id))
    return profesional


def profesional_de_usuario(session: Session, usuario_id: uuid.UUID) -> Profesional | None:
    """Perfil de profesional asociado a un usuario autenticado, si existe."""
    return ProfesionalRepository(session).por_usuario_id(usuario_id)


def esta_asignado_a_menor(session: Session, profesional_id: uuid.UUID, menor_id: uuid.UUID) -> bool:
    return MenorProfesionalRepository(session).asignacion(menor_id, profesional_id) is not None


def es_defensor_asignado(session: Session, usuario_id: uuid.UUID, menor_id: uuid.UUID) -> bool:
    """¿El usuario autenticado es el profesional con cargo=defensor asignado a ese menor?"""
    profesional = profesional_de_usuario(session, usuario_id)
    if profesional is None or profesional.cargo != "defensor":
        return False
    return esta_asignado_a_menor(session, profesional.id, menor_id)


def menores_asignados_a_profesional(session: Session, profesional_id: uuid.UUID) -> list[MenorProfesional]:
    return MenorProfesionalRepository(session).listar_por_profesional(profesional_id)


def profesionales_asignados_a_menor(session: Session, menor_id: uuid.UUID) -> list[MenorProfesional]:
    return MenorProfesionalRepository(session).listar_por_menor(menor_id)
