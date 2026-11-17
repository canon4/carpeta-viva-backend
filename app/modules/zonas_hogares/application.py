"""Zonas y Hogares: Casos de uso.

Organiza los hogares sustitutos por zona y guarda los datos de cada hogar.

Las importaciones de otros módulos (`madres`, `profesionales`, `asignaciones`) se hacen dentro
de cada función para evitar ciclos de importación entre capas de aplicación hermanas, igual que
en `menores`/`asignaciones`/`documentos`.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido
from app.modules.auth.domain import Rol

from .domain import validar_capacidad
from .models import HogarSustituto, Zona
from .repository import HogarRepository, ZonaRepository
from .schemas import HogarCreate, HogarUpdate, ZonaCreate, ZonaUpdate


def crear_zona(session: Session, datos: ZonaCreate, usuario_id: uuid.UUID) -> Zona:
    zona = ZonaRepository(session).crear(Zona(nombre=datos.nombre, descripcion=datos.descripcion))
    registrar_acceso(session, accion="zona_creada", usuario_id=usuario_id, recurso=str(zona.id))
    return zona


def _es_coordinador(usuario) -> bool:
    return usuario is not None and usuario.rol == Rol.COORDINADOR.value


def _exigir_zona_propia(session: Session, usuario, zona_id: uuid.UUID | None, accion: str, recurso: str) -> None:
    """El coordinador solo actúa sobre su zona (ADR-0007 §2.2, RN03). Deniega por defecto si no
    tiene zona y registra el intento denegado en auditoría. Admin no tiene restricción."""
    if not _es_coordinador(usuario):
        return
    if usuario.zona_id is None or zona_id != usuario.zona_id:
        registrar_acceso(session, accion=f"{accion}_denegado", usuario_id=usuario.id, recurso=recurso)
        raise prohibido()


def listar_zonas(session: Session, usuario=None) -> list[Zona]:
    zonas = ZonaRepository(session).listar()
    if _es_coordinador(usuario):
        return [z for z in zonas if usuario.zona_id is not None and z.id == usuario.zona_id]
    return zonas


def obtener_zona_visible(session: Session, zona_id: uuid.UUID, usuario) -> Zona:
    zona = obtener_zona(session, zona_id)
    _exigir_zona_propia(session, usuario, zona.id, "zona_lectura", str(zona_id))
    return zona


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


def crear_hogar(session: Session, datos: HogarCreate, usuario_id: uuid.UUID, usuario=None) -> HogarSustituto:
    validar_capacidad(datos.capacidad_maxima)
    obtener_zona(session, datos.zona_id)
    _exigir_zona_propia(session, usuario, datos.zona_id, "hogar_creacion", str(datos.zona_id))
    hogar = HogarSustituto(
        zona_id=datos.zona_id,
        capacidad_maxima=datos.capacidad_maxima,
        fecha_habilitacion=datos.fecha_habilitacion,
    )
    hogar = HogarRepository(session).crear(hogar)
    registrar_acceso(session, accion="hogar_creado", usuario_id=usuario_id, recurso=str(hogar.id))
    return hogar


def listar_hogares(session: Session, zona_id: uuid.UUID | None = None, usuario=None) -> list[HogarSustituto]:
    if _es_coordinador(usuario):
        if zona_id is not None:
            _exigir_zona_propia(session, usuario, zona_id, "hogares_listado", str(zona_id))
        if usuario.zona_id is None:
            return []
        zona_id = usuario.zona_id
    return HogarRepository(session).listar(zona_id)


def hogar_de_madre(session: Session, madre_id: uuid.UUID) -> HogarSustituto | None:
    """El hogar de una madre (si tiene uno asignado). Lo usa el módulo `madres` para que la madre
    conozca el id de su propio hogar sin necesitar acceso a Zonas y Hogares (roles coordinador/
    admin, ver `_coordinador_o_admin` en `api.py`)."""
    return HogarRepository(session).por_madre_id(madre_id)


def obtener_hogar(session: Session, hogar_id: uuid.UUID) -> HogarSustituto:
    hogar = HogarRepository(session).por_id(hogar_id)
    if hogar is None:
        raise no_encontrado("Hogar sustituto no encontrado")
    return hogar


def obtener_hogar_visible(session: Session, hogar_id: uuid.UUID, usuario) -> HogarSustituto:
    hogar = obtener_hogar(session, hogar_id)
    _exigir_zona_propia(session, usuario, hogar.zona_id, "hogar_lectura", str(hogar_id))
    return hogar


def actualizar_hogar(
    session: Session, hogar_id: uuid.UUID, datos: HogarUpdate, usuario_id: uuid.UUID, usuario=None
) -> HogarSustituto:
    from app.modules.madres.repository import MadreRepository  # evita import circular entre módulos

    hogar = obtener_hogar(session, hogar_id)
    _exigir_zona_propia(session, usuario, hogar.zona_id, "hogar_actualizacion", str(hogar_id))
    if datos.capacidad_maxima is not None:
        validar_capacidad(datos.capacidad_maxima)
        hogar.capacidad_maxima = datos.capacidad_maxima
    if datos.madre_id is not None:
        if MadreRepository(session).por_id(datos.madre_id) is None:
            raise no_encontrado("Madre sustituta no encontrada")
        otro = HogarRepository(session).por_madre_id(datos.madre_id)
        if otro is not None and otro.id != hogar.id:
            # Una madre tiene un solo hogar (RN01). Reasignarla desde otro hogar, quizá de otra
            # zona, le daría acceso a los NNA de este hogar sin pasar por su coordinador.
            raise ValueError("La madre ya está vinculada a otro hogar")
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


def coordinador_puede_ver_madre(session: Session, usuario, madre_id: uuid.UUID) -> bool:
    """Coordinador: ve a una madre si su hogar está en su zona o si todavía no tiene hogar (madres
    disponibles para vincular). Para cualquier otro rol devuelve True: el rol ya lo filtró la API."""
    if not _es_coordinador(usuario):
        return True
    hogar = HogarRepository(session).por_madre_id(madre_id)
    if hogar is None:
        return True
    return usuario.zona_id is not None and hogar.zona_id == usuario.zona_id


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
