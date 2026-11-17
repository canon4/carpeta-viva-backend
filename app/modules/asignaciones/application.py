"""Asignaciones y Traslados: Casos de uso.

Vincula al menor con el hogar con fecha de inicio y fin; actas de traslado.

Las importaciones de otros módulos (`menores`, `profesionales`, `zonas_hogares`, `madres`) se hacen
dentro de cada función para evitar ciclos entre capas de aplicación hermanas.
"""
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido
from app.modules.auth.domain import Rol

from .models import Asignacion, AsignacionHistory
from .repository import AsignacionHistoryRepository, AsignacionRepository
from .schemas import AsignacionCerrar, AsignacionCreate


def _asignacion_o_404(session: Session, asignacion_id: uuid.UUID) -> Asignacion:
    asignacion = AsignacionRepository(session).por_id(asignacion_id)
    if asignacion is None:
        raise no_encontrado("Asignación no encontrada")
    return asignacion


def _puede_gestionar(session: Session, usuario, menor_id: uuid.UUID, hogar_id: uuid.UUID | None = None) -> bool:
    """Autorización de escritura (crear/cerrar asignación). Deniega por defecto si falta contexto
    (zona del coordinador o hogar de destino): nunca se concede por ausencia de datos."""
    rol = usuario.rol
    if rol == Rol.ADMIN.value:
        return True
    if rol == Rol.COORDINADOR.value:
        if usuario.zona_id is None or hogar_id is None:
            return False
        from app.modules.zonas_hogares.application import obtener_hogar

        hogar = obtener_hogar(session, hogar_id)
        return hogar.zona_id == usuario.zona_id
    if rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        from app.modules.profesionales.application import es_defensor_asignado

        return es_defensor_asignado(session, usuario.id, menor_id)
    return False


def _visible_asignacion(session: Session, usuario, asignacion: Asignacion) -> bool:
    """Visibilidad de lectura por fila (ADR-0007, mismo criterio que `menores._puede_ver_menor`,
    aplicado aquí porque `asignaciones` expone sus propios endpoints de lectura)."""
    rol = usuario.rol
    if rol in (Rol.ADMIN.value, Rol.AUDITOR.value):
        return True
    if rol == Rol.COORDINADOR.value:
        if usuario.zona_id is None:
            return False
        from app.modules.zonas_hogares.application import obtener_hogar

        hogar = obtener_hogar(session, asignacion.hogar_id)
        return hogar.zona_id == usuario.zona_id
    if rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        from app.modules.profesionales.application import esta_asignado_a_menor, profesional_de_usuario

        profesional = profesional_de_usuario(session, usuario.id)
        return profesional is not None and esta_asignado_a_menor(session, profesional.id, asignacion.menor_id)
    if rol == Rol.MADRE.value:
        from app.modules.menores.application import puede_ver_menor

        return puede_ver_menor(session, usuario, asignacion.menor_id)
    return False


def _snapshot(asignacion: Asignacion, cambiado_por: uuid.UUID | None) -> AsignacionHistory:
    return AsignacionHistory(
        asignacion_id=asignacion.id,
        version=asignacion.version,
        menor_id=asignacion.menor_id,
        hogar_id=asignacion.hogar_id,
        fecha_inicio=asignacion.fecha_inicio,
        fecha_fin=asignacion.fecha_fin,
        estado=asignacion.estado,
        tipo_movimiento=asignacion.tipo_movimiento,
        acta_referencia=asignacion.acta_referencia,
        motivo=asignacion.motivo,
        cambiado_por=cambiado_por,
    )


def _revocar_permisos_madre_saliente(session: Session, asignacion: Asignacion, actor_id: uuid.UUID) -> None:
    from app.modules.madres.repository import MadreRepository
    from app.modules.menores.application import revocar_permisos_de_usuario
    from app.modules.zonas_hogares.application import obtener_hogar

    hogar = obtener_hogar(session, asignacion.hogar_id)
    if hogar.madre_id is None:
        return
    madre = MadreRepository(session).por_id(hogar.madre_id)
    if madre is None or madre.usuario_id is None:
        return
    revocar_permisos_de_usuario(session, asignacion.menor_id, madre.usuario_id, actor_id=actor_id)


def crear_asignacion(session: Session, usuario, datos: AsignacionCreate) -> Asignacion:
    if not _puede_gestionar(session, usuario, datos.menor_id, datos.hogar_id):
        registrar_acceso(
            session, accion="asignacion_creacion_denegada", usuario_id=usuario.id, menor_id=datos.menor_id
        )
        raise prohibido()

    repo = AsignacionRepository(session)
    vigente = repo.vigente_por_menor(datos.menor_id)

    if datos.tipo_movimiento.value == "ingreso":
        if vigente is not None:
            raise ValueError("El menor ya tiene una asignación vigente; use tipo_movimiento=traslado")
    elif datos.tipo_movimiento.value == "traslado":
        if vigente is None:
            raise ValueError("No hay asignación vigente para trasladar; use tipo_movimiento=ingreso")
        if vigente.hogar_id == datos.hogar_id:
            raise ValueError("El hogar de destino es el mismo hogar actual")
        # El coordinador debe administrar también la zona de origen: si no, podría traer a su
        # zona (y pasar a ver) un NNA de otra zona (ADR-0007 §2.2).
        if usuario.rol == Rol.COORDINADOR.value and not _puede_gestionar(
            session, usuario, datos.menor_id, vigente.hogar_id
        ):
            registrar_acceso(
                session, accion="asignacion_creacion_denegada", usuario_id=usuario.id, menor_id=datos.menor_id
            )
            raise prohibido()
    else:
        raise ValueError("tipo_movimiento debe ser 'ingreso' o 'traslado' al crear una asignación")

    if vigente is not None and datos.tipo_movimiento.value == "traslado":
        history_repo = AsignacionHistoryRepository(session)
        history_repo.crear(_snapshot(vigente, usuario.id))
        vigente.fecha_fin = datos.fecha_inicio
        vigente.estado = "cerrada"
        vigente.version += 1
        _revocar_permisos_madre_saliente(session, vigente, usuario.id)

    nueva = Asignacion(
        menor_id=datos.menor_id,
        hogar_id=datos.hogar_id,
        fecha_inicio=datos.fecha_inicio,
        estado="vigente",
        version=1,
        tipo_movimiento=datos.tipo_movimiento.value,
        acta_referencia=datos.acta_referencia,
        motivo=datos.motivo,
        registrado_por=usuario.id,
    )
    repo.crear(nueva)
    repo.commit()

    registrar_acceso(
        session,
        accion=f"asignacion_{datos.tipo_movimiento.value}",
        usuario_id=usuario.id,
        recurso=str(nueva.id),
        menor_id=nueva.menor_id,
    )
    return nueva


def listar_asignaciones(
    session: Session,
    menor_id: uuid.UUID | None = None,
    hogar_id: uuid.UUID | None = None,
    zona_id: uuid.UUID | None = None,
    madre_id: uuid.UUID | None = None,
    estado: str | None = None,
) -> list[Asignacion]:
    """Uso interno (sin control de autorización): el llamador ya debe pertenecer a una capa de
    aplicación que filtró por permisos (p. ej. `menores.application`). No exponer directo en `api.py`;
    para el endpoint público usar `listar_asignaciones_visibles`."""
    return AsignacionRepository(session).listar(
        menor_id=menor_id, hogar_id=hogar_id, zona_id=zona_id, madre_id=madre_id, estado=estado
    )


def listar_asignaciones_visibles(
    session: Session,
    usuario,
    menor_id: uuid.UUID | None = None,
    hogar_id: uuid.UUID | None = None,
    zona_id: uuid.UUID | None = None,
    estado: str | None = None,
) -> list[Asignacion]:
    """Listado para el endpoint público: aplica visibilidad por fila según el rol (ADR-0007).
    Ignora los filtros de zona/hogar que el llamador no está autorizado a ver en vez de confiar en
    los que llegan por query string."""
    rol = usuario.rol

    if rol in (Rol.ADMIN.value, Rol.AUDITOR.value):
        resultado = listar_asignaciones(session, menor_id=menor_id, hogar_id=hogar_id, zona_id=zona_id, estado=estado)
    elif rol == Rol.COORDINADOR.value:
        if usuario.zona_id is None:
            resultado = []
        else:
            resultado = listar_asignaciones(
                session, menor_id=menor_id, hogar_id=hogar_id, zona_id=usuario.zona_id, estado=estado
            )
    elif rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        from app.modules.profesionales.application import menores_asignados_a_profesional, profesional_de_usuario

        profesional = profesional_de_usuario(session, usuario.id)
        if profesional is None:
            resultado = []
        else:
            asignados = {mp.menor_id for mp in menores_asignados_a_profesional(session, profesional.id)}
            crudo = listar_asignaciones(session, menor_id=menor_id, hogar_id=hogar_id, estado=estado)
            resultado = [a for a in crudo if a.menor_id in asignados]
    elif rol == Rol.MADRE.value:
        from app.modules.madres.application import madre_de_usuario

        madre = madre_de_usuario(session, usuario.id)
        if madre is None:
            resultado = []
        else:
            # RF7: la madre solo ve asignaciones vigentes de su hogar (nunca el historial de un
            # menor que ya salió); se ignora cualquier `estado` solicitado distinto.
            resultado = listar_asignaciones(session, menor_id=menor_id, hogar_id=hogar_id, madre_id=madre.id, estado="vigente")
    else:
        resultado = []

    registrar_acceso(session, accion="asignaciones_listadas", usuario_id=usuario.id)
    return resultado


def obtener_asignacion(session: Session, usuario, asignacion_id: uuid.UUID) -> Asignacion:
    asignacion = _asignacion_o_404(session, asignacion_id)
    if not _visible_asignacion(session, usuario, asignacion):
        registrar_acceso(
            session,
            accion="asignacion_consulta_denegada",
            usuario_id=usuario.id,
            recurso=str(asignacion.id),
            menor_id=asignacion.menor_id,
        )
        raise prohibido()
    registrar_acceso(
        session,
        accion="asignacion_consultada",
        usuario_id=usuario.id,
        recurso=str(asignacion.id),
        menor_id=asignacion.menor_id,
    )
    return asignacion


def vigente_de_menor(session: Session, menor_id: uuid.UUID) -> Asignacion | None:
    """Uso interno (sin control de autorización), ver nota de `listar_asignaciones`."""
    return AsignacionRepository(session).vigente_por_menor(menor_id)


def historial_asignacion_interno(session: Session, asignacion_id: uuid.UUID) -> list[AsignacionHistory]:
    """Uso interno (sin control de autorización) para el manifiesto del paquete de archivo
    (ADR-0010, sección 3.2). No exponer en `api.py`."""
    return AsignacionHistoryRepository(session).listar_por_asignacion(asignacion_id)


def vigente_de_menor_visible(session: Session, usuario, menor_id: uuid.UUID) -> Asignacion | None:
    """Para el endpoint público: solo responde si el usuario puede ver ese menor. Se reutiliza
    `menores.application.puede_ver_menor`, que ya cubre las cinco reglas de fila de ADR-0007
    (admin/auditor, coordinador por zona vía la asignación vigente, profesional/defensor asignado,
    madre con asignación vigente en su hogar)."""
    from app.modules.menores.application import puede_ver_menor

    if not puede_ver_menor(session, usuario, menor_id):
        registrar_acceso(session, accion="asignacion_vigente_denegada", usuario_id=usuario.id, menor_id=menor_id)
        raise prohibido()

    registrar_acceso(session, accion="asignacion_vigente_consultada", usuario_id=usuario.id, menor_id=menor_id)
    return vigente_de_menor(session, menor_id)


def cerrar_asignacion(session: Session, usuario, asignacion_id: uuid.UUID, datos: AsignacionCerrar) -> Asignacion:
    asignacion = _asignacion_o_404(session, asignacion_id)
    if not _puede_gestionar(session, usuario, asignacion.menor_id, asignacion.hogar_id):
        registrar_acceso(
            session,
            accion="asignacion_cierre_denegado",
            usuario_id=usuario.id,
            recurso=str(asignacion.id),
            menor_id=asignacion.menor_id,
        )
        raise prohibido()
    if asignacion.estado != "vigente":
        raise ValueError("La asignación ya está cerrada")

    history_repo = AsignacionHistoryRepository(session)
    history_repo.crear(_snapshot(asignacion, usuario.id))

    asignacion.fecha_fin = datos.fecha_fin or date.today()
    asignacion.estado = "cerrada"
    asignacion.tipo_movimiento = "egreso"
    if datos.motivo is not None:
        asignacion.motivo = datos.motivo
    if datos.acta_referencia is not None:
        asignacion.acta_referencia = datos.acta_referencia
    asignacion.version += 1

    _revocar_permisos_madre_saliente(session, asignacion, usuario.id)

    from app.modules.menores.application import actualizar_estado_por_cierre

    AsignacionRepository(session).commit()
    actualizar_estado_por_cierre(
        session,
        asignacion.menor_id,
        "egresado",
        motivo="Egreso por cierre de asignación",
        actor_id=usuario.id,
    )

    registrar_acceso(
        session,
        accion="asignacion_cerrada",
        usuario_id=usuario.id,
        recurso=str(asignacion.id),
        menor_id=asignacion.menor_id,
    )
    return asignacion


def historial_asignacion(session: Session, usuario, asignacion_id: uuid.UUID) -> list[AsignacionHistory]:
    """Historial de movimientos de una asignación. La madre nunca lo ve (igual que
    `menores.historial_menor`): expone traslados/motivos que exceden lo que RF7 le habilita."""
    asignacion = _asignacion_o_404(session, asignacion_id)
    if usuario.rol == Rol.MADRE.value or not _visible_asignacion(session, usuario, asignacion):
        registrar_acceso(
            session,
            accion="historial_asignacion_denegado",
            usuario_id=usuario.id,
            recurso=str(asignacion.id),
            menor_id=asignacion.menor_id,
        )
        raise prohibido()
    registrar_acceso(
        session,
        accion="historial_asignacion_consultado",
        usuario_id=usuario.id,
        recurso=str(asignacion.id),
        menor_id=asignacion.menor_id,
    )
    return AsignacionHistoryRepository(session).listar_por_asignacion(asignacion_id)
