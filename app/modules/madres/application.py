"""Madres Sustitutas: Casos de uso.

Datos de la madre sustituta: identificación, certificación y firma única.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido

from .models import MadreSustituta
from .repository import MadreRepository
from .schemas import MadreCreate, MadreOut, MadreUpdate


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


def _visible_para(session: Session, usuario, madre_id: uuid.UUID) -> bool:
    """Coordinador acotado a su zona (RN03): ve madres de hogares de su zona y madres sin hogar."""
    if usuario is None:
        return True
    from app.modules.zonas_hogares.application import coordinador_puede_ver_madre  # evita ciclo

    return coordinador_puede_ver_madre(session, usuario, madre_id)


def listar_madres(session: Session, usuario=None) -> list[MadreSustituta]:
    return [m for m in MadreRepository(session).listar() if _visible_para(session, usuario, m.id)]


def obtener_madre(session: Session, madre_id: uuid.UUID, usuario=None) -> MadreSustituta:
    madre = MadreRepository(session).por_id(madre_id)
    if madre is None:
        raise no_encontrado("Madre sustituta no encontrada")
    if not _visible_para(session, usuario, madre.id):
        registrar_acceso(session, accion="madre_acceso_denegado", usuario_id=usuario.id, recurso=str(madre_id))
        raise prohibido()
    return madre


def actualizar_madre(
    session: Session, madre_id: uuid.UUID, datos: MadreUpdate, usuario_id: uuid.UUID, usuario=None
) -> MadreSustituta:
    madre = obtener_madre(session, madre_id, usuario)
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


def obtener_mi_perfil_con_hogar(session: Session, usuario_id: uuid.UUID) -> MadreOut:
    """Perfil de la madre autenticada con el id de su propio hogar (si tiene uno asignado), para
    que pueda usar Inventario, Alimentos y el Asistente de IA sin conocer el id de memoria: la
    madre no tiene acceso a Zonas y Hogares (roles coordinador/admin)."""
    from app.modules.zonas_hogares.application import hogar_de_madre  # evita import circular

    madre = obtener_mi_perfil(session, usuario_id)
    hogar = hogar_de_madre(session, madre.id)
    salida = MadreOut.model_validate(madre)
    salida.hogar_id = hogar.id if hogar else None
    return salida


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
