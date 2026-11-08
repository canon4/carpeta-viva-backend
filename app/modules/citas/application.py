"""Citas y Recordatorios: casos de uso (ADR-0009, sección 2).

"El sistema no las asigna, solo recuerda" (CLAUDE.md). Autorización de fila = `puede_ver_menor`;
escritura = `puede_ver_menor` y no auditor. `puede_ver_notas` expone la corrección de seguridad
(`notas` se oculta a quien no tenga `tiene_permiso_seccion`): el filtrado real se aplica en
`api.py` sobre el esquema de salida, nunca mutando la entidad ORM.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido
from app.modules.auth.domain import Rol

from .domain import ESTADOS_CITA, seccion_de_tipo_cita
from .models import Cita
from .repository import CitaRepository
from .schemas import CitaCreate, CitaUpdate


def _cita_o_404(session: Session, cita_id: uuid.UUID) -> Cita:
    cita = CitaRepository(session).por_id(cita_id)
    if cita is None:
        raise no_encontrado("Cita no encontrada")
    return cita


def _puede_ver(session: Session, usuario, menor_id: uuid.UUID) -> bool:
    from app.modules.menores.application import puede_ver_menor

    return puede_ver_menor(session, usuario, menor_id)


def _puede_escribir(session: Session, usuario, menor_id: uuid.UUID) -> bool:
    return usuario.rol != Rol.AUDITOR.value and _puede_ver(session, usuario, menor_id)


def _sin_zona(dt: datetime) -> datetime:
    """Normaliza a UTC naive para comparar: SQLite (pruebas) devuelve `DateTime(timezone=True)`
    sin tzinfo, PostgreSQL (producción) sí la conserva. Sin esto, comparar ambos backends con un
    `datetime` aware revienta con `TypeError` en SQLite."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def puede_ver_notas(session: Session, usuario, cita: Cita) -> bool:
    """Corrección obligatoria de seguridad (ADR-0009, sección 2): a diferencia del resto de la
    fila, `notas` exige `tiene_permiso_seccion` sobre la sección mapeada del tipo de cita.
    `otro` no tiene sección sensible asociada, visible a quien tenga `puede_ver_menor`."""
    seccion = seccion_de_tipo_cita(cita.tipo)
    if seccion is None:
        return True
    from app.modules.menores.application import tiene_permiso_seccion

    return tiene_permiso_seccion(session, usuario, cita.menor_id, seccion)


def crear_cita(session: Session, usuario, datos: CitaCreate) -> Cita:
    from app.modules.archivo.application import esta_archivado

    if not _puede_escribir(session, usuario, datos.menor_id):
        registrar_acceso(
            session, accion="cita_creacion_denegada", usuario_id=usuario.id, menor_id=datos.menor_id
        )
        raise prohibido()
    if esta_archivado(session, datos.menor_id):
        registrar_acceso(
            session, accion="cita_creacion_denegada_archivado", usuario_id=usuario.id, menor_id=datos.menor_id
        )
        raise prohibido("El expediente está archivado; no se pueden crear citas nuevas")
    cita = Cita(
        menor_id=datos.menor_id,
        tipo=datos.tipo,
        fecha_hora=datos.fecha_hora,
        lugar=datos.lugar,
        notas=datos.notas,
        estado="pendiente",
        registrado_por=usuario.id,
    )
    cita = CitaRepository(session).crear(cita)
    registrar_acceso(
        session, accion="cita_creada", usuario_id=usuario.id, recurso=str(cita.id), menor_id=cita.menor_id
    )
    return cita


def listar_citas(
    session: Session,
    usuario,
    menor_id: uuid.UUID | None = None,
    tipo: str | None = None,
    estado: str | None = None,
) -> list[Cita]:
    crudo = CitaRepository(session).listar(menor_id=menor_id, tipo=tipo, estado=estado)
    resultado = [c for c in crudo if _puede_ver(session, usuario, c.menor_id)]
    registrar_acceso(session, accion="citas_listadas", usuario_id=usuario.id)
    return resultado


def listar_proximas(session: Session, usuario) -> list[Cita]:
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    crudo = [
        c for c in CitaRepository(session).listar(estado="pendiente") if _sin_zona(c.fecha_hora) >= ahora
    ]
    resultado = [c for c in crudo if _puede_ver(session, usuario, c.menor_id)]
    registrar_acceso(session, accion="citas_proximas_consultadas", usuario_id=usuario.id)
    return resultado


def obtener_cita(session: Session, usuario, cita_id: uuid.UUID) -> Cita:
    cita = _cita_o_404(session, cita_id)
    if not _puede_ver(session, usuario, cita.menor_id):
        registrar_acceso(
            session, accion="cita_consulta_denegada", usuario_id=usuario.id, recurso=str(cita.id), menor_id=cita.menor_id
        )
        raise prohibido()
    registrar_acceso(
        session, accion="cita_consultada", usuario_id=usuario.id, recurso=str(cita.id), menor_id=cita.menor_id
    )
    return cita


def actualizar_cita(session: Session, usuario, cita_id: uuid.UUID, datos: CitaUpdate) -> Cita:
    cita = _cita_o_404(session, cita_id)
    if not _puede_escribir(session, usuario, cita.menor_id):
        registrar_acceso(
            session, accion="cita_edicion_denegada", usuario_id=usuario.id, recurso=str(cita.id), menor_id=cita.menor_id
        )
        raise prohibido()
    if datos.fecha_hora is not None:
        cita.fecha_hora = datos.fecha_hora
    if datos.lugar is not None:
        cita.lugar = datos.lugar
    if datos.notas is not None:
        cita.notas = datos.notas
    cita = CitaRepository(session).guardar(cita)
    registrar_acceso(
        session, accion="cita_actualizada", usuario_id=usuario.id, recurso=str(cita.id), menor_id=cita.menor_id
    )
    return cita


def cambiar_estado_cita(session: Session, usuario, cita_id: uuid.UUID, estado: str) -> Cita:
    if estado not in ESTADOS_CITA:
        raise ValueError(f"estado debe ser uno de {ESTADOS_CITA}")
    cita = _cita_o_404(session, cita_id)
    if not _puede_escribir(session, usuario, cita.menor_id):
        registrar_acceso(
            session, accion="cita_cambio_estado_denegado", usuario_id=usuario.id, recurso=str(cita.id), menor_id=cita.menor_id
        )
        raise prohibido()
    cita.estado = estado
    cita = CitaRepository(session).guardar(cita)
    registrar_acceso(
        session, accion="cita_estado_actualizado", usuario_id=usuario.id, recurso=str(cita.id), menor_id=cita.menor_id
    )
    return cita


def listar_citas_interno(session: Session, menor_id: uuid.UUID) -> list[Cita]:
    """Uso interno (sin control de autorización) para el manifiesto del paquete de archivo
    (ADR-0010, sección 3.2). No exponer en `api.py`."""
    return CitaRepository(session).listar(menor_id=menor_id)


def citas_vencidas_pendientes(session: Session) -> list[Cita]:
    """Uso interno desde `alertas` (ADR-0009, RF9 visita_vencida): sin control de autorización,
    mismo patrón que `asignaciones.listar_asignaciones`. No exponer directo en `api.py`."""
    return CitaRepository(session).vencidas_pendientes(datetime.now(timezone.utc).replace(tzinfo=None))
