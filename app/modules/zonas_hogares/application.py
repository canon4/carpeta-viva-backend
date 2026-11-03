"""Zonas y Hogares: Casos de uso.

Organiza los hogares sustitutos por zona y guarda los datos de cada hogar.

Las importaciones de otros módulos (`madres`, `profesionales`, `asignaciones`) se hacen dentro
de cada función para evitar ciclos de importación entre capas de aplicación hermanas, igual que
en `menores`/`asignaciones`/`documentos`.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado
from app.modules.auth.domain import Rol

from .domain import validar_capacidad
from .models import HogarSustituto, Zona
from .repository import HogarRepository, ZonaRepository
from .schemas import HogarCreate, HogarUpdate, ZonaCreate, ZonaUpdate


def crear_zona(session: Session, datos: ZonaCreate, usuario_id: uuid.UUID) -> Zona:
    zona = ZonaRepository(session).crear(Zona(nombre=datos.nombre, descripcion=datos.descripcion))
    registrar_acceso(session, accion="zona_creada", usuario_id=usuario_id, recurso=str(zona.id))
    return zona


def listar_zonas(session: Session) -> list[Zona]:
    return ZonaRepository(session).listar()


def obtener_zona(session: Session, zona_id: uuid.UUID) -> Zona:
    zona = ZonaRepository(session).por_id(zona_id)
    if zona is None:
        raise no_encontrado("Zona no encontrada")
    return zona


def actualizar_zona(session: Session, zona_id: uuid.UUID, datos: ZonaUpdate, usuario_id: uuid.UUID) -> Zona:
    zona = obtener_zona(session, zona_id)
    if datos.nombre is not None:
        zona.nombre = datos.nombre
    if datos.descripcion is not None:
        zona.descripcion = datos.descripcion
    zona = ZonaRepository(session).guardar(zona)
    registrar_acceso(session, accion="zona_actualizada", usuario_id=usuario_id, recurso=str(zona.id))
    return zona


def crear_hogar(session: Session, datos: HogarCreate, usuario_id: uuid.UUID) -> HogarSustituto:
    validar_capacidad(datos.capacidad_maxima)
    obtener_zona(session, datos.zona_id)
    hogar = HogarSustituto(
        zona_id=datos.zona_id,
        capacidad_maxima=datos.capacidad_maxima,
        fecha_habilitacion=datos.fecha_habilitacion,
    )
    hogar = HogarRepository(session).crear(hogar)
    registrar_acceso(session, accion="hogar_creado", usuario_id=usuario_id, recurso=str(hogar.id))
    return hogar


def listar_hogares(session: Session, zona_id: uuid.UUID | None = None) -> list[HogarSustituto]:
    return HogarRepository(session).listar(zona_id)


def obtener_hogar(session: Session, hogar_id: uuid.UUID) -> HogarSustituto:
    hogar = HogarRepository(session).por_id(hogar_id)
    if hogar is None:
        raise no_encontrado("Hogar sustituto no encontrado")
    return hogar


def actualizar_hogar(session: Session, hogar_id: uuid.UUID, datos: HogarUpdate, usuario_id: uuid.UUID) -> HogarSustituto:
    from app.modules.madres.repository import MadreRepository  # evita import circular entre módulos

    hogar = obtener_hogar(session, hogar_id)
    if datos.capacidad_maxima is not None:
        validar_capacidad(datos.capacidad_maxima)
        hogar.capacidad_maxima = datos.capacidad_maxima
    if datos.madre_id is not None:
        if MadreRepository(session).por_id(datos.madre_id) is None:
            raise no_encontrado("Madre sustituta no encontrada")
        hogar.madre_id = datos.madre_id
    if datos.estado is not None:
        hogar.estado = datos.estado.value
    hogar = HogarRepository(session).guardar(hogar)
    registrar_acceso(session, accion="hogar_actualizado", usuario_id=usuario_id, recurso=str(hogar.id))
    return hogar


def _profesional_tiene_menor_en_hogar(session: Session, usuario_id: uuid.UUID, hogar_id: uuid.UUID) -> bool:
    """¿El profesional/defensor autenticado tiene algún menor asignado cuya asignación vigente
    apunta a ese hogar? (ADR-0009, sección 0)."""
    from app.modules.asignaciones.application import vigente_de_menor
    from app.modules.profesionales.application import menores_asignados_a_profesional, profesional_de_usuario

    profesional = profesional_de_usuario(session, usuario_id)
    if profesional is None:
        return False
    for mp in menores_asignados_a_profesional(session, profesional.id):
        vigente = vigente_de_menor(session, mp.menor_id)
        if vigente is not None and vigente.hogar_id == hogar_id:
            return True
    return False


def puede_ver_hogar(session: Session, usuario, hogar_id: uuid.UUID) -> bool:
    """Autorización de lectura por hogar (ADR-0009, sección 0), reutilizada por `inventario` y
    `alimentos` (y, en una limpieza futura no bloqueante, por `documentos`)."""
    rol = usuario.rol
    if rol in (Rol.ADMIN.value, Rol.AUDITOR.value):
        return True
    hogar = obtener_hogar(session, hogar_id)
    if rol == Rol.COORDINADOR.value:
        return usuario.zona_id is not None and hogar.zona_id == usuario.zona_id
    if rol == Rol.MADRE.value:
        from app.modules.madres.application import madre_de_usuario

        madre = madre_de_usuario(session, usuario.id)
        return madre is not None and hogar.madre_id == madre.id
    if rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        return _profesional_tiene_menor_en_hogar(session, usuario.id, hogar_id)
    return False


def puede_gestionar_hogar(session: Session, usuario, hogar_id: uuid.UUID) -> bool:
    """Igual que `puede_ver_hogar` pero excluye al auditor (nunca crea/edita, solo lee)."""
    if usuario.rol == Rol.AUDITOR.value:
        return False
    return puede_ver_hogar(session, usuario, hogar_id)
