"""Madres Sustitutas: Casos de uso.

Datos de la madre sustituta: identificación, certificación y firma única.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado

from .models import MadreSustituta
from .repository import MadreRepository
from .schemas import MadreCreate, MadreUpdate


def crear_madre(session: Session, datos: MadreCreate, usuario_id: uuid.UUID) -> MadreSustituta:
    madre = MadreSustituta(
        usuario_id=datos.usuario_id,
        nombres=datos.nombres,
        apellidos=datos.apellidos,
        numero_identificacion=datos.numero_identificacion,
        direccion=datos.direccion,
        telefono=datos.telefono,
    )
    madre = MadreRepository(session).crear(madre)
    registrar_acceso(session, accion="madre_creada", usuario_id=usuario_id, recurso=str(madre.id))
    return madre


def listar_madres(session: Session) -> list[MadreSustituta]:
    return MadreRepository(session).listar()


def obtener_madre(session: Session, madre_id: uuid.UUID) -> MadreSustituta:
    madre = MadreRepository(session).por_id(madre_id)
    if madre is None:
        raise no_encontrado("Madre sustituta no encontrada")
    return madre


def actualizar_madre(session: Session, madre_id: uuid.UUID, datos: MadreUpdate, usuario_id: uuid.UUID) -> MadreSustituta:
    madre = obtener_madre(session, madre_id)
    if datos.direccion is not None:
        madre.direccion = datos.direccion
    if datos.telefono is not None:
        madre.telefono = datos.telefono
    if datos.estado_certificacion is not None:
        madre.estado_certificacion = datos.estado_certificacion.value
    madre = MadreRepository(session).guardar(madre)
    registrar_acceso(session, accion="madre_actualizada", usuario_id=usuario_id, recurso=str(madre.id))
    return madre


def obtener_mi_perfil(session: Session, usuario_id: uuid.UUID) -> MadreSustituta:
    madre = MadreRepository(session).por_usuario_id(usuario_id)
    if madre is None:
        raise no_encontrado("No hay perfil de madre sustituta asociado a este usuario")
    return madre


def madre_de_usuario(session: Session, usuario_id: uuid.UUID) -> MadreSustituta | None:
    """Perfil de madre sustituta asociado a un usuario autenticado, si existe (no lanza error)."""
    return MadreRepository(session).por_usuario_id(usuario_id)


def actualizar_mi_firma(session: Session, usuario_id: uuid.UUID, firma_ref: str) -> MadreSustituta:
    # Nota: el almacenamiento cifrado de la firma queda pendiente (ADR futuro).
    # Para esta demo solo se guarda la referencia (ruta o base64 corto) en texto plano.
    madre = obtener_mi_perfil(session, usuario_id)
    madre.firma_ref = firma_ref
    madre = MadreRepository(session).guardar(madre)
    registrar_acceso(session, accion="firma_cargada", usuario_id=usuario_id, recurso=str(madre.id))
    return madre
