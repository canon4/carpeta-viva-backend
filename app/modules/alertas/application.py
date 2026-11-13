"""Alertas y Evasiones: casos de uso (ADR-0009, sección 1).

Evasión, visitas vencidas (RF9) y el panel de alertas. Las importaciones de otros módulos
(`menores`, `profesionales`, `asignaciones`, `zonas_hogares`, `madres`, `auth`, `citas`) se hacen
dentro de cada función para evitar ciclos entre capas de aplicación hermanas (mismo patrón que
`documentos`/`menores`).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.config import get_settings
from app.core.errors import no_encontrado, prohibido
from app.modules.auth.domain import Rol

from .domain import ROLES_DESTINATARIOS_EVASION
from .models import Alerta, AlertaDestinatario
from .repository import AlertaDestinatarioRepository, AlertaRepository, ConfiguracionAlertasRepository
from .schemas import (
    ContactoEmergencia,
    ContactosEmergenciaOut,
    EvasionCreate,
    TelefonoPoliciaInfanciaOut,
)


# ---------------------------------------------------------------------------
# Configuración editable por admin (migración 0008)
# ---------------------------------------------------------------------------

def _telefono_policia_infancia(session: Session) -> str:
    """Valor en uso ahora mismo: el editado por `admin` si existe, si no el de
    `POLICIA_INFANCIA_TELEFONO` (entorno)."""
    configuracion = ConfiguracionAlertasRepository(session).obtener()
    return configuracion.telefono_policia_infancia or get_settings().policia_infancia_telefono


def obtener_telefono_policia_infancia(session: Session, usuario) -> TelefonoPoliciaInfanciaOut:
    """`GET /alertas/configuracion/telefono-policia-infancia` (admin, sección "Configuración
    editable"): consulta del valor vigente y de dónde sale, para la pantalla de administración."""
    if usuario.rol != Rol.ADMIN.value:
        registrar_acceso(session, accion="configuracion_alertas_consulta_denegada", usuario_id=usuario.id)
        raise prohibido()
    configuracion = ConfiguracionAlertasRepository(session).obtener()
    if configuracion.telefono_policia_infancia:
        return TelefonoPoliciaInfanciaOut(telefono=configuracion.telefono_policia_infancia, editado_por_admin=True)
    return TelefonoPoliciaInfanciaOut(telefono=get_settings().policia_infancia_telefono, editado_por_admin=False)


def actualizar_telefono_policia_infancia(session: Session, usuario, telefono: str) -> TelefonoPoliciaInfanciaOut:
    """`PUT /alertas/configuracion/telefono-policia-infancia`: solo `admin`, sin redespliegue
    (a diferencia de la variable de entorno que reemplaza, ver migración 0008)."""
    if usuario.rol != Rol.ADMIN.value:
        registrar_acceso(session, accion="configuracion_alertas_edicion_denegada", usuario_id=usuario.id)
        raise prohibido()
    repo = ConfiguracionAlertasRepository(session)
    configuracion = repo.obtener()
    configuracion.telefono_policia_infancia = telefono.strip()
    configuracion.actualizado_en = datetime.now(timezone.utc)
    configuracion.actualizado_por = usuario.id
    repo.guardar(configuracion)
    registrar_acceso(session, accion="configuracion_alertas_telefono_policia_actualizado", usuario_id=usuario.id)
    return TelefonoPoliciaInfanciaOut(telefono=configuracion.telefono_policia_infancia, editado_por_admin=True)


# ---------------------------------------------------------------------------
# Resolución de destinatarios y contactos de emergencia
# ---------------------------------------------------------------------------

def _resolver_destinatarios(session: Session, menor_id: uuid.UUID, tipo: str) -> list[uuid.UUID]:
    """ADR-0009, sección "Resolución de destinatarios", con la corrección obligatoria de
    seguridad: una alerta de evasión nunca queda con cero destinatarios."""
    from app.modules.profesionales.application import obtener_profesional, profesionales_asignados_a_menor

    asignaciones_prof = profesionales_asignados_a_menor(session, menor_id)
    destinatarios: set[uuid.UUID] = set()

    if tipo == "evasion":
        for mp in asignaciones_prof:
            if mp.rol_asignado in ROLES_DESTINATARIOS_EVASION:
                profesional = obtener_profesional(session, mp.profesional_id)
                if profesional.usuario_id is not None:
                    destinatarios.add(profesional.usuario_id)

        if not destinatarios:
            # Corrección obligatoria (ADR-0009, revisión de seguridad punto 1): respaldo con el
            # coordinador de la zona del hogar vigente y, en su defecto, cualquier admin.
            from app.modules.asignaciones.application import vigente_de_menor
            from app.modules.auth.application import usuarios_por_rol
            from app.modules.zonas_hogares.application import obtener_hogar

            zona_id = None
            vigente = vigente_de_menor(session, menor_id)
            if vigente is not None:
                hogar = obtener_hogar(session, vigente.hogar_id)
                zona_id = hogar.zona_id

            respaldo = []
            if zona_id is not None:
                respaldo = usuarios_por_rol(session, Rol.COORDINADOR.value, zona_id=zona_id)
            if not respaldo:
                respaldo = usuarios_por_rol(session, Rol.ADMIN.value)
            destinatarios.update(u.id for u in respaldo)
        return list(destinatarios)

    # visita_vencida / documento_faltante: todos los profesionales asignados + la madre vigente.
    for mp in asignaciones_prof:
        profesional = obtener_profesional(session, mp.profesional_id)
        if profesional.usuario_id is not None:
            destinatarios.add(profesional.usuario_id)

    from app.modules.asignaciones.application import vigente_de_menor
    from app.modules.madres.application import obtener_madre
    from app.modules.zonas_hogares.application import obtener_hogar

    vigente = vigente_de_menor(session, menor_id)
    if vigente is not None:
        hogar = obtener_hogar(session, vigente.hogar_id)
        if hogar.madre_id is not None:
            madre = obtener_madre(session, hogar.madre_id)
            if madre.usuario_id is not None:
                destinatarios.add(madre.usuario_id)
    return list(destinatarios)


def _contactos_emergencia(session: Session, menor_id: uuid.UUID) -> ContactosEmergenciaOut:
    """ADR-0009, sección 1: policía (número estático) + defensor/psicosocial resueltos. Si el
    profesional asignado no tiene teléfono, o no hay profesional asignado a ese rol, se dice
    explícitamente en `nota` (no se omite el campo en silencio)."""
    from app.modules.profesionales.application import obtener_profesional, profesionales_asignados_a_menor

    asignaciones_prof = profesionales_asignados_a_menor(session, menor_id)
    por_rol = {
        mp.rol_asignado: mp.profesional_id for mp in asignaciones_prof if mp.rol_asignado in ROLES_DESTINATARIOS_EVASION
    }

    contactos: list[ContactoEmergencia] = []
    for rol in ROLES_DESTINATARIOS_EVASION:
        profesional_id = por_rol.get(rol)
        if profesional_id is None:
            contactos.append(
                ContactoEmergencia(rol_asignado=rol, nota=f"Sin profesional con rol {rol} asignado a este menor")
            )
            continue
        profesional = obtener_profesional(session, profesional_id)
        nota = None if profesional.telefono else "Teléfono no registrado para este profesional"
        contactos.append(
            ContactoEmergencia(
                rol_asignado=rol,
                nombres=f"{profesional.nombres} {profesional.apellidos}",
                telefono=profesional.telefono,
                nota=nota,
            )
        )
    return ContactosEmergenciaOut(policia_infancia_telefono=_telefono_policia_infancia(session), contactos=contactos)


def _crear_destinatarios(session: Session, alerta: Alerta) -> list[AlertaDestinatario]:
    ids = _resolver_destinatarios(session, alerta.menor_id, alerta.tipo)
    repo = AlertaDestinatarioRepository(session)
    return [repo.crear(AlertaDestinatario(alerta_id=alerta.id, usuario_id=uid)) for uid in ids]


def _adjuntar_destinatarios(session: Session, alerta: Alerta) -> Alerta:
    alerta.destinatarios = AlertaDestinatarioRepository(session).listar_por_alerta(alerta.id)
    return alerta


# ---------------------------------------------------------------------------
# Autorización
# ---------------------------------------------------------------------------

def _alerta_o_404(session: Session, alerta_id: uuid.UUID) -> Alerta:
    alerta = AlertaRepository(session).por_id(alerta_id)
    if alerta is None:
        raise no_encontrado("Alerta no encontrada")
    return alerta


def _es_destinatario(session: Session, usuario_id: uuid.UUID, alerta_id: uuid.UUID) -> bool:
    return AlertaDestinatarioRepository(session).por_alerta_y_usuario(alerta_id, usuario_id) is not None


def _coordinador_ve_menor(session: Session, usuario, menor_id: uuid.UUID) -> bool:
    if usuario.zona_id is None:
        return False
    from app.modules.asignaciones.application import vigente_de_menor
    from app.modules.zonas_hogares.application import obtener_hogar

    vigente = vigente_de_menor(session, menor_id)
    if vigente is None:
        return False
    hogar = obtener_hogar(session, vigente.hogar_id)
    return hogar.zona_id == usuario.zona_id


def _puede_ver_alerta(session: Session, usuario, alerta: Alerta) -> bool:
    """ADR-0009, sección 1 "Autorización": destinatario, quien la generó, coordinador de zona,
    admin o auditor (metadatos)."""
    rol = usuario.rol
    if rol in (Rol.ADMIN.value, Rol.AUDITOR.value):
        return True
    if _es_destinatario(session, usuario.id, alerta.id):
        return True
    if alerta.generada_por is not None and usuario.id == alerta.generada_por:
        return True
    if rol == Rol.COORDINADOR.value:
        return _coordinador_ve_menor(session, usuario, alerta.menor_id)
    return False


def _puede_cerrar_alerta(session: Session, usuario, alerta: Alerta) -> bool:
    rol = usuario.rol
    if rol == Rol.ADMIN.value:
        return True
    if rol == Rol.COORDINADOR.value:
        return _coordinador_ve_menor(session, usuario, alerta.menor_id)
    if alerta.generada_por is not None and usuario.id == alerta.generada_por:
        return True
    if rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        from app.modules.profesionales.application import esta_asignado_a_menor, profesional_de_usuario

        profesional = profesional_de_usuario(session, usuario.id)
        return profesional is not None and esta_asignado_a_menor(session, profesional.id, alerta.menor_id)
    return False


# ---------------------------------------------------------------------------
# Evasión
# ---------------------------------------------------------------------------

def reportar_evasion(session: Session, usuario, datos: EvasionCreate) -> tuple[Alerta, ContactosEmergenciaOut]:
    from app.modules.archivo.application import esta_archivado
    from app.modules.menores.application import puede_ver_menor

    if usuario.rol == Rol.AUDITOR.value or not puede_ver_menor(session, usuario, datos.menor_id):
        registrar_acceso(
            session, accion="evasion_reporte_denegado", usuario_id=usuario.id, menor_id=datos.menor_id
        )
        raise prohibido()
    if esta_archivado(session, datos.menor_id):
        registrar_acceso(
            session, accion="evasion_reporte_denegado_archivado", usuario_id=usuario.id, menor_id=datos.menor_id
        )
        raise prohibido("El expediente está archivado; no se pueden crear alertas nuevas")

    alerta = Alerta(
        tipo="evasion",
        menor_id=datos.menor_id,
        origen="manual",
        generada_por=usuario.id,
        descripcion=datos.descripcion,
        detalle=None,
        estado="activa",
    )
    alerta = AlertaRepository(session).crear(alerta)
    _crear_destinatarios(session, alerta)
    _adjuntar_destinatarios(session, alerta)
    contactos = _contactos_emergencia(session, datos.menor_id)

    if not alerta.destinatarios:
        # Red de seguridad operacional: el respaldo de `_resolver_destinatarios` cubre
        # defensor/psicosocial sin cuenta (cae a coordinador, luego a admin), pero si ni
        # siquiera existe un usuario `admin` en el sistema, la lista queda vacía. Nunca debe
        # pasar en silencio: se deja una marca de auditoría explícita y detectable para que
        # `admin`/`datos-infra` lo note (el reporte y los contactos de emergencia en pantalla
        # ya llegaron de todos modos a quien reportó, eso no depende de esto).
        registrar_acceso(
            session,
            accion="evasion_sin_destinatarios_resolubles",
            usuario_id=usuario.id,
            recurso=str(alerta.id),
            menor_id=alerta.menor_id,
        )

    registrar_acceso(
        session, accion="evasion_reportada", usuario_id=usuario.id, recurso=str(alerta.id), menor_id=alerta.menor_id
    )
    return alerta, contactos


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

def listar_alertas_interno(session: Session, menor_id: uuid.UUID) -> list[Alerta]:
    """Uso interno (sin control de autorización) para el manifiesto del paquete de archivo
    (ADR-0010, sección 3.2): incluye alertas activas y cerradas. No exponer en `api.py`."""
    return AlertaRepository(session).listar(menor_id=menor_id)


def listar_alertas(
    session: Session,
    usuario,
    menor_id: uuid.UUID | None = None,
    tipo: str | None = None,
    estado: str | None = None,
) -> list[Alerta]:
    crudo = AlertaRepository(session).listar(menor_id=menor_id, tipo=tipo, estado=estado)
    resultado = [a for a in crudo if _puede_ver_alerta(session, usuario, a)]
    for alerta in resultado:
        _adjuntar_destinatarios(session, alerta)
    registrar_acceso(session, accion="alertas_listadas", usuario_id=usuario.id)
    return resultado


def obtener_alerta(session: Session, usuario, alerta_id: uuid.UUID) -> Alerta:
    alerta = _alerta_o_404(session, alerta_id)
    if not _puede_ver_alerta(session, usuario, alerta):
        registrar_acceso(
            session, accion="alerta_consulta_denegada", usuario_id=usuario.id, recurso=str(alerta.id), menor_id=alerta.menor_id
        )
        raise prohibido()
    _adjuntar_destinatarios(session, alerta)
    registrar_acceso(
        session, accion="alerta_consultada", usuario_id=usuario.id, recurso=str(alerta.id), menor_id=alerta.menor_id
    )
    return alerta


def mis_pendientes(session: Session, usuario) -> list[Alerta]:
    pendientes = AlertaDestinatarioRepository(session).listar_pendientes_de_usuario(usuario.id)
    repo_alerta = AlertaRepository(session)
    alertas = []
    for destinatario in pendientes:
        alerta = repo_alerta.por_id(destinatario.alerta_id)
        if alerta is not None:
            _adjuntar_destinatarios(session, alerta)
            alertas.append(alerta)
    registrar_acceso(session, accion="alertas_mis_pendientes_consultadas", usuario_id=usuario.id)
    return alertas


def marcar_visto(session: Session, usuario, alerta_id: uuid.UUID) -> AlertaDestinatario:
    _alerta_o_404(session, alerta_id)
    repo = AlertaDestinatarioRepository(session)
    destinatario = repo.por_alerta_y_usuario(alerta_id, usuario.id)
    if destinatario is None:
        registrar_acceso(
            session, accion="alerta_visto_denegado", usuario_id=usuario.id, recurso=str(alerta_id)
        )
        raise prohibido("Solo un destinatario puede marcar esta alerta como vista")
    destinatario.visto_en = datetime.now(timezone.utc)
    destinatario = repo.guardar(destinatario)
    registrar_acceso(
        session, accion="alerta_vista", usuario_id=usuario.id, recurso=str(alerta_id)
    )
    return destinatario


def cerrar_alerta(session: Session, usuario, alerta_id: uuid.UUID) -> Alerta:
    alerta = _alerta_o_404(session, alerta_id)
    if not _puede_cerrar_alerta(session, usuario, alerta):
        registrar_acceso(
            session, accion="alerta_cierre_denegado", usuario_id=usuario.id, recurso=str(alerta.id), menor_id=alerta.menor_id
        )
        raise prohibido()
    alerta.estado = "cerrada"
    alerta = AlertaRepository(session).guardar(alerta)
    _adjuntar_destinatarios(session, alerta)
    registrar_acceso(
        session, accion="alerta_cerrada", usuario_id=usuario.id, recurso=str(alerta.id), menor_id=alerta.menor_id
    )
    return alerta


# ---------------------------------------------------------------------------
# Generación automática (RF9) y panel
# ---------------------------------------------------------------------------

def _generar_visita_vencida_automaticas(session: Session) -> list[Alerta]:
    """Idempotente: no duplica una alerta activa ya abierta para la misma cita. Solo
    `visita_vencida` en esta fase (`documento_faltante` queda bloqueado, ver ADR-0009)."""
    from app.modules.citas.application import citas_vencidas_pendientes

    existentes = AlertaRepository(session).listar(tipo="visita_vencida", estado="activa")
    citas_con_alerta = {
        str(existente.detalle.get("cita_id")) for existente in existentes if existente.detalle
    }

    creadas: list[Alerta] = []
    for cita in citas_vencidas_pendientes(session):
        if str(cita.id) in citas_con_alerta:
            continue
        alerta = Alerta(
            tipo="visita_vencida",
            menor_id=cita.menor_id,
            origen="automatica",
            generada_por=None,
            descripcion=f"Cita {cita.tipo} vencida sin atender ({cita.fecha_hora.isoformat()})",
            detalle={"cita_id": str(cita.id)},
            estado="activa",
        )
        alerta = AlertaRepository(session).crear(alerta)
        _crear_destinatarios(session, alerta)
        creadas.append(alerta)
    return creadas


def _generar_documento_faltante_automaticas(session: Session) -> list[Alerta]:
    """ADR-0010, sección 1.7: "sin informe psicosocial en 60 días", conectada aquí con el mismo
    mecanismo de generación automática que ya existe para `visita_vencida` (ADR-0009). Idempotente:
    no duplica una alerta activa ya abierta para el mismo menor y categoría."""
    from app.modules.ia.application import evaluar_documento_faltante

    existentes = AlertaRepository(session).listar(tipo="documento_faltante", estado="activa")
    menores_con_alerta = {
        existente.menor_id
        for existente in existentes
        if existente.detalle and existente.detalle.get("categoria") == "psicosocial"
    }

    creadas: list[Alerta] = []
    for menor_id in evaluar_documento_faltante(session):
        if menor_id in menores_con_alerta:
            continue
        alerta = Alerta(
            tipo="documento_faltante",
            menor_id=menor_id,
            origen="automatica",
            generada_por=None,
            descripcion="Sin informe psicosocial registrado en los últimos 60 días",
            detalle={"categoria": "psicosocial", "plazo_dias": 60},
            estado="activa",
        )
        alerta = AlertaRepository(session).crear(alerta)
        _crear_destinatarios(session, alerta)
        creadas.append(alerta)
    return creadas


def _generar_indexacion_pendiente_automaticas(session: Session) -> list[Alerta]:
    """ADR-0010, sección 1.3 (corrección de seguridad): si la indexación de IA en segundo plano
    falla o se pierde a medias, un documento/reporte puede quedar sin fragmentos indefinidamente
    sin que nadie lo note. Esta alerta hace visible esa falla (panel de `admin`, que ve todas las
    alertas activas sin filtrar por destinatario) sin depender de que alguien ejecute
    `POST /ia/mantenimiento/reindexar-pendientes` por iniciativa propia."""
    from app.modules.ia.application import evaluar_indexacion_pendiente

    existentes = AlertaRepository(session).listar(tipo="indexacion_pendiente", estado="activa")
    recursos_con_alerta = {
        (existente.detalle.get("tipo_recurso"), existente.detalle.get("recurso_id"))
        for existente in existentes
        if existente.detalle
    }

    creadas: list[Alerta] = []
    for tipo_recurso, recurso_id, menor_id in evaluar_indexacion_pendiente(session):
        clave = (tipo_recurso, str(recurso_id))
        if clave in recursos_con_alerta:
            continue
        alerta = Alerta(
            tipo="indexacion_pendiente",
            menor_id=menor_id,
            origen="automatica",
            generada_por=None,
            descripcion=f"{tipo_recurso.capitalize()} sin indexar para búsqueda de IA hace más de una hora",
            detalle={"tipo_recurso": tipo_recurso, "recurso_id": str(recurso_id)},
            estado="activa",
        )
        alerta = AlertaRepository(session).crear(alerta)
        _crear_destinatarios(session, alerta)
        creadas.append(alerta)
    return creadas


def _generar_automaticas_todas(session: Session) -> list[Alerta]:
    return (
        _generar_visita_vencida_automaticas(session)
        + _generar_documento_faltante_automaticas(session)
        + _generar_indexacion_pendiente_automaticas(session)
    )


def generar_automaticas(session: Session, usuario) -> list[Alerta]:
    if usuario.rol not in (Rol.COORDINADOR.value, Rol.ADMIN.value):
        registrar_acceso(session, accion="alertas_generacion_denegada", usuario_id=usuario.id)
        raise prohibido()
    creadas = _generar_automaticas_todas(session)
    for alerta in creadas:
        _adjuntar_destinatarios(session, alerta)
    registrar_acceso(session, accion="alertas_generadas_automaticas", usuario_id=usuario.id)
    return creadas


def panel(session: Session, usuario) -> list[Alerta]:
    """GET /alertas/panel: dispara el barrido automático y devuelve alertas activas visibles
    (coordinador por zona, profesional por sus menores asignados, admin todas)."""
    _generar_automaticas_todas(session)

    rol = usuario.rol
    activas = AlertaRepository(session).listar(estado="activa")

    if rol == Rol.ADMIN.value:
        alertas = activas
    elif rol == Rol.COORDINADOR.value:
        alertas = [a for a in activas if _coordinador_ve_menor(session, usuario, a.menor_id)]
    elif rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        from app.modules.profesionales.application import menores_asignados_a_profesional, profesional_de_usuario

        profesional = profesional_de_usuario(session, usuario.id)
        if profesional is None:
            alertas = []
        else:
            menor_ids = {mp.menor_id for mp in menores_asignados_a_profesional(session, profesional.id)}
            alertas = [a for a in activas if a.menor_id in menor_ids]
    else:
        alertas = []

    for alerta in alertas:
        _adjuntar_destinatarios(session, alerta)
    registrar_acceso(session, accion="alertas_panel_consultado", usuario_id=usuario.id)
    return alertas
