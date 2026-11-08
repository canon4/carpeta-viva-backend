"""Menores y Expedientes: Casos de uso.

Carpeta digital de cada menor: datos personales, padres, historial médico y psicosocial, estado.

Autorización por fila y por sección (ADR-0007), denegar por defecto. Las importaciones de otros
módulos (`profesionales`, `madres`, `asignaciones`, `zonas_hogares`) se hacen dentro de cada función
(no al cargar el módulo) para evitar ciclos de importación entre capas de aplicación hermanas.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido
from app.modules.auth.domain import Rol

from .domain import CARGO_DEFENSOR, cambios_trackeados
from .models import Menor, MenorFamiliar, MenorHistory, PermisoExpediente
from .repository import (
    MenorFamiliarRepository,
    MenorHistoryRepository,
    MenorRepository,
    PermisoExpedienteRepository,
)
from .schemas import FamiliarCreate, HogarPanelGroup, MenorCreate, MenorUpdate, PermisoCreate, ZonaPanelGroup


def _menor_o_404(session: Session, menor_id: uuid.UUID) -> Menor:
    menor = MenorRepository(session).por_id(menor_id)
    if menor is None:
        raise no_encontrado("Menor no encontrado")
    return menor


def _puede_ver_menor(session: Session, usuario, menor: Menor) -> bool:
    """Visibilidad de fila: regla de autorización de ADR-0007, sección 2."""
    rol = usuario.rol
    if rol in (Rol.ADMIN.value, Rol.AUDITOR.value):
        return True

    if rol == Rol.COORDINADOR.value:
        if usuario.zona_id is None:
            return False
        from app.modules.asignaciones.application import vigente_de_menor
        from app.modules.zonas_hogares.application import obtener_hogar

        vigente = vigente_de_menor(session, menor.id)
        if vigente is None:
            return False
        hogar = obtener_hogar(session, vigente.hogar_id)
        return hogar.zona_id == usuario.zona_id

    if rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        from app.modules.profesionales.application import esta_asignado_a_menor, profesional_de_usuario

        profesional = profesional_de_usuario(session, usuario.id)
        return profesional is not None and esta_asignado_a_menor(session, profesional.id, menor.id)

    if rol == Rol.MADRE.value:
        from app.modules.asignaciones.application import vigente_de_menor
        from app.modules.madres.application import madre_de_usuario
        from app.modules.zonas_hogares.application import obtener_hogar

        madre = madre_de_usuario(session, usuario.id)
        if madre is None:
            return False
        vigente = vigente_de_menor(session, menor.id)
        if vigente is None:
            return False
        hogar = obtener_hogar(session, vigente.hogar_id)
        return hogar.madre_id == madre.id

    return False


def _tiene_permiso_seccion(session: Session, usuario, menor: Menor, seccion: str) -> bool:
    """Visibilidad de una sección sensible (familia, salud, psicosocial)."""
    rol = usuario.rol
    if rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        from app.modules.profesionales.application import esta_asignado_a_menor, profesional_de_usuario

        profesional = profesional_de_usuario(session, usuario.id)
        return profesional is not None and esta_asignado_a_menor(session, profesional.id, menor.id)

    if rol == Rol.MADRE.value:
        if not _puede_ver_menor(session, usuario, menor):
            return False
        return seccion in PermisoExpedienteRepository(session).secciones_activas(menor.id, usuario.id)

    # Coordinador y auditor: sin secciones sensibles por defecto (ADR-0007, puntos 2 y 3).
    return False


def tiene_permiso_seccion(session: Session, usuario, menor_id: uuid.UUID, seccion: str) -> bool:
    """Wrapper público de `_tiene_permiso_seccion` para otros módulos (p. ej. `documentos`), mismo
    patrón que `puede_ver_menor` (ADR-0008, sección 4): recibe `menor_id`, no la entidad."""
    menor = MenorRepository(session).por_id(menor_id)
    if menor is None:
        return False
    return _tiene_permiso_seccion(session, usuario, menor, seccion)


def menor_por_id_interno(session: Session, menor_id: uuid.UUID) -> Menor:
    """Uso interno (sin control de autorización), para `archivo.application` (ADR-0010, sección
    3.1/3.2): la condición de archivo se evalúa precisamente cuando ya no hay asignación vigente,
    así que `puede_ver_menor` (que depende de esa asignación para coordinador/madre) no sirve aquí.
    El llamador ya resuelve su propia autorización de zona antes de invocar esto. No exponer en
    `api.py`; mismo patrón que `asignaciones.vigente_de_menor`."""
    return _menor_o_404(session, menor_id)


def historial_menor_interno(session: Session, menor_id: uuid.UUID) -> list[MenorHistory]:
    """Uso interno (sin control de autorización) para el manifiesto del paquete de archivo
    (ADR-0010, sección 3.2). No exponer en `api.py`."""
    return MenorHistoryRepository(session).listar_por_menor(menor_id)


def permisos_interno(session: Session, menor_id: uuid.UUID) -> list[PermisoExpediente]:
    """Uso interno (sin control de autorización) para el manifiesto del paquete de archivo
    (ADR-0010, sección 3.2): incluye permisos activos e inactivos (historial de ACL). No
    exponer en `api.py`."""
    return PermisoExpedienteRepository(session).listar_por_menor(menor_id)


def puede_ver_menor(session: Session, usuario, menor_id: uuid.UUID) -> bool:
    """Wrapper público de `_puede_ver_menor` para otros módulos (p. ej. `asignaciones`) que necesitan
    aplicar la misma regla de visibilidad por fila sin acceder directamente al repositorio."""
    menor = MenorRepository(session).por_id(menor_id)
    if menor is None:
        return False
    return _puede_ver_menor(session, usuario, menor)


def _puede_editar_menor(session: Session, usuario, menor: Menor) -> bool:
    rol = usuario.rol
    if rol == Rol.ADMIN.value:
        return True
    if rol == Rol.COORDINADOR.value:
        return _puede_ver_menor(session, usuario, menor)
    if rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        from app.modules.profesionales.application import esta_asignado_a_menor, profesional_de_usuario

        profesional = profesional_de_usuario(session, usuario.id)
        return profesional is not None and esta_asignado_a_menor(session, profesional.id, menor.id)
    return False


def crear_menor(session: Session, usuario, datos: MenorCreate) -> Menor:
    rol = usuario.rol
    if rol not in (Rol.COORDINADOR.value, Rol.ADMIN.value, Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        registrar_acceso(session, accion="menor_creacion_denegada", usuario_id=usuario.id)
        raise prohibido()
    if rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        from app.modules.profesionales.application import profesional_de_usuario

        profesional = profesional_de_usuario(session, usuario.id)
        if profesional is None or profesional.cargo != CARGO_DEFENSOR:
            registrar_acceso(session, accion="menor_creacion_denegada", usuario_id=usuario.id)
            raise prohibido()

    menor = Menor(
        nombres=datos.nombres,
        apellidos=datos.apellidos,
        fecha_nacimiento=datos.fecha_nacimiento,
        genero=datos.genero,
        tipo_documento=datos.tipo_documento.value if datos.tipo_documento else None,
        numero_documento=datos.numero_documento,
        estado_actual="activo",
        version=1,
    )
    menor = MenorRepository(session).crear(menor)
    registrar_acceso(session, accion="menor_creado", usuario_id=usuario.id, recurso=str(menor.id), menor_id=menor.id)
    return menor


def listar_menores(
    session: Session,
    usuario,
    zona_id: uuid.UUID | None = None,
    hogar_id: uuid.UUID | None = None,
    estado: str | None = None,
) -> list[Menor]:
    rol = usuario.rol

    if rol in (Rol.ADMIN.value, Rol.AUDITOR.value):
        menores = MenorRepository(session).listar(estado)
        if zona_id is not None or hogar_id is not None:
            vigentes = _vigentes_filtrados(session, zona_id, hogar_id)
            menores = [m for m in menores if m.id in vigentes]
        return menores

    if rol == Rol.COORDINADOR.value:
        if usuario.zona_id is None:
            return []
        vigentes = _vigentes_filtrados(session, usuario.zona_id, hogar_id)
        menores = [m for m in MenorRepository(session).listar(estado) if m.id in vigentes]
        return menores

    if rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        from app.modules.profesionales.application import menores_asignados_a_profesional, profesional_de_usuario

        profesional = profesional_de_usuario(session, usuario.id)
        if profesional is None:
            return []
        asignados = {mp.menor_id for mp in menores_asignados_a_profesional(session, profesional.id)}
        menores = [m for m in MenorRepository(session).listar(estado) if m.id in asignados]
        if zona_id is not None or hogar_id is not None:
            vigentes = _vigentes_filtrados(session, zona_id, hogar_id)
            menores = [m for m in menores if m.id in vigentes]
        return menores

    if rol == Rol.MADRE.value:
        from app.modules.asignaciones.application import listar_asignaciones
        from app.modules.madres.application import madre_de_usuario

        madre = madre_de_usuario(session, usuario.id)
        if madre is None:
            return []
        vigentes = listar_asignaciones(session, estado="vigente", madre_id=madre.id)
        menores = [MenorRepository(session).por_id(a.menor_id) for a in vigentes]
        menores = [m for m in menores if m is not None and (estado is None or m.estado_actual == estado)]
        return menores

    raise prohibido()


def _vigentes_filtrados(
    session: Session, zona_id: uuid.UUID | None, hogar_id: uuid.UUID | None
) -> set[uuid.UUID]:
    from app.modules.asignaciones.application import listar_asignaciones

    asignaciones = listar_asignaciones(session, zona_id=zona_id, hogar_id=hogar_id, estado="vigente")
    return {a.menor_id for a in asignaciones}


def obtener_menor(session: Session, usuario, menor_id: uuid.UUID) -> Menor:
    menor = _menor_o_404(session, menor_id)
    if not _puede_ver_menor(session, usuario, menor):
        registrar_acceso(
            session, accion="menor_consulta_denegada", usuario_id=usuario.id, recurso=str(menor.id), menor_id=menor.id
        )
        raise prohibido()
    registrar_acceso(
        session, accion="menor_consultado", usuario_id=usuario.id, recurso=str(menor.id), menor_id=menor.id
    )
    return menor


def _aplicar_cambios(session: Session, menor: Menor, cambios: dict, actor_id: uuid.UUID, motivo: str | None) -> Menor:
    """Snapshot + aplica cambios + sube versión, en una sola transacción (ADR-0007, patrón *_History)."""
    if cambios_trackeados(menor, cambios):
        snapshot = MenorHistory(
            menor_id=menor.id,
            version=menor.version,
            nombres=menor.nombres,
            apellidos=menor.apellidos,
            fecha_nacimiento=menor.fecha_nacimiento,
            genero=menor.genero,
            tipo_documento=menor.tipo_documento,
            numero_documento=menor.numero_documento,
            estado_actual=menor.estado_actual,
            cambiado_por=actor_id,
            motivo=motivo,
        )
        MenorHistoryRepository(session).crear(snapshot)
        menor.version += 1

    for campo, valor in cambios.items():
        if valor is not None:
            setattr(menor, campo, valor)

    return MenorRepository(session).guardar(menor)


def actualizar_menor(session: Session, usuario, menor_id: uuid.UUID, datos: MenorUpdate) -> Menor:
    menor = _menor_o_404(session, menor_id)
    if not _puede_editar_menor(session, usuario, menor):
        registrar_acceso(
            session, accion="menor_edicion_denegada", usuario_id=usuario.id, recurso=str(menor.id), menor_id=menor.id
        )
        raise prohibido()

    cambios = {
        "nombres": datos.nombres,
        "apellidos": datos.apellidos,
        "fecha_nacimiento": datos.fecha_nacimiento,
        "genero": datos.genero,
        "tipo_documento": datos.tipo_documento.value if datos.tipo_documento else None,
        "numero_documento": datos.numero_documento,
        "estado_actual": datos.estado_actual.value if datos.estado_actual else None,
    }
    menor = _aplicar_cambios(session, menor, cambios, actor_id=usuario.id, motivo=datos.motivo)
    registrar_acceso(
        session, accion="menor_actualizado", usuario_id=usuario.id, recurso=str(menor.id), menor_id=menor.id
    )
    return menor


def actualizar_estado_por_cierre(
    session: Session, menor_id: uuid.UUID, estado_actual: str, motivo: str | None, actor_id: uuid.UUID
) -> Menor:
    """Uso interno desde `asignaciones.cerrar_asignacion` (RF7: egreso). Quien llama ya validó autorización
    sobre la asignación que dispara este cambio; no se repite el chequeo de permisos de edición del menor
    (que depende de la asignación vigente que, en este punto del flujo, ya puede estar cerrada)."""
    menor = _menor_o_404(session, menor_id)
    menor = _aplicar_cambios(session, menor, {"estado_actual": estado_actual}, actor_id=actor_id, motivo=motivo)
    registrar_acceso(session, accion="menor_actualizado", usuario_id=actor_id, recurso=str(menor.id), menor_id=menor.id)
    return menor


def historial_menor(session: Session, usuario, menor_id: uuid.UUID) -> list[MenorHistory]:
    menor = _menor_o_404(session, menor_id)
    if usuario.rol == Rol.MADRE.value or not _puede_ver_menor(session, usuario, menor):
        registrar_acceso(
            session,
            accion="historial_menor_denegado",
            usuario_id=usuario.id,
            recurso=str(menor.id),
            menor_id=menor.id,
        )
        raise prohibido()
    registrar_acceso(
        session, accion="historial_menor_consultado", usuario_id=usuario.id, recurso=str(menor.id), menor_id=menor.id
    )
    return MenorHistoryRepository(session).listar_por_menor(menor.id)


def listar_familiares(session: Session, usuario, menor_id: uuid.UUID) -> list[MenorFamiliar]:
    menor = _menor_o_404(session, menor_id)
    if not _tiene_permiso_seccion(session, usuario, menor, "familia"):
        registrar_acceso(
            session,
            accion="familiares_acceso_denegado",
            usuario_id=usuario.id,
            recurso=str(menor.id),
            menor_id=menor.id,
        )
        raise prohibido()
    registrar_acceso(
        session, accion="familiares_consultados", usuario_id=usuario.id, recurso=str(menor.id), menor_id=menor.id
    )
    return MenorFamiliarRepository(session).listar_por_menor(menor.id)


def crear_familiar(session: Session, usuario, menor_id: uuid.UUID, datos: FamiliarCreate) -> MenorFamiliar:
    menor = _menor_o_404(session, menor_id)
    rol = usuario.rol
    permitido = False
    if rol == Rol.ADMIN.value:
        permitido = True
    elif rol == Rol.COORDINADOR.value:
        permitido = _puede_ver_menor(session, usuario, menor)
    elif rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        permitido = _tiene_permiso_seccion(session, usuario, menor, "familia")
    if not permitido:
        registrar_acceso(
            session,
            accion="familiar_creacion_denegada",
            usuario_id=usuario.id,
            recurso=str(menor.id),
            menor_id=menor.id,
        )
        raise prohibido()

    familiar = MenorFamiliar(
        menor_id=menor.id,
        parentesco=datos.parentesco.value,
        nombres=datos.nombres,
        numero_identificacion=datos.numero_identificacion,
        telefono=datos.telefono,
        direccion=datos.direccion,
        estado_vital=datos.estado_vital.value,
        observaciones=datos.observaciones,
    )
    familiar = MenorFamiliarRepository(session).crear(familiar)
    registrar_acceso(
        session, accion="familiar_creado", usuario_id=usuario.id, recurso=str(familiar.id), menor_id=menor.id
    )
    return familiar


def listar_permisos(session: Session, usuario, menor_id: uuid.UUID) -> list[PermisoExpediente]:
    menor = _menor_o_404(session, menor_id)
    if not _tiene_permiso_seccion(session, usuario, menor, "familia") and usuario.rol != Rol.ADMIN.value:
        registrar_acceso(
            session,
            accion="permisos_acceso_denegado",
            usuario_id=usuario.id,
            recurso=str(menor.id),
            menor_id=menor.id,
        )
        raise prohibido()
    registrar_acceso(
        session, accion="permisos_consultados", usuario_id=usuario.id, recurso=str(menor.id), menor_id=menor.id
    )
    return PermisoExpedienteRepository(session).listar_por_menor(menor.id)


def crear_permiso(session: Session, usuario, menor_id: uuid.UUID, datos: PermisoCreate) -> PermisoExpediente:
    """Solo el profesional con cargo=defensor asignado a ese menor puede otorgar permisos (ADR-0007, punto 5)."""
    menor = _menor_o_404(session, menor_id)
    from app.modules.auth.repository import UsuarioRepository
    from app.modules.profesionales.application import es_defensor_asignado

    if not es_defensor_asignado(session, usuario.id, menor.id):
        registrar_acceso(
            session,
            accion="permiso_otorgar_denegado",
            usuario_id=usuario.id,
            recurso=str(menor.id),
            menor_id=menor.id,
        )
        raise prohibido("Solo el defensor asignado a este menor puede otorgar este permiso")

    destinatario = UsuarioRepository(session).por_id(datos.usuario_id)
    if destinatario is None or destinatario.rol != Rol.MADRE.value:
        raise ValueError("El permiso solo puede otorgarse a un usuario con rol madre")

    repo = PermisoExpedienteRepository(session)
    existente = repo.buscar(menor.id, datos.seccion.value, datos.usuario_id)
    if existente is not None:
        existente.activo = True
        existente.notas = datos.notas
        existente.otorgado_por = usuario.id
        permiso = repo.guardar(existente)
    else:
        permiso = repo.crear(
            PermisoExpediente(
                menor_id=menor.id,
                seccion=datos.seccion.value,
                usuario_id=datos.usuario_id,
                otorgado_por=usuario.id,
                notas=datos.notas,
            )
        )
    registrar_acceso(
        session, accion="permiso_otorgado", usuario_id=usuario.id, recurso=str(permiso.id), menor_id=menor.id
    )
    return permiso


def revocar_permiso(session: Session, usuario, menor_id: uuid.UUID, permiso_id: uuid.UUID) -> PermisoExpediente:
    menor = _menor_o_404(session, menor_id)
    from app.modules.profesionales.application import es_defensor_asignado

    if not es_defensor_asignado(session, usuario.id, menor.id):
        registrar_acceso(
            session,
            accion="permiso_revocar_denegado",
            usuario_id=usuario.id,
            recurso=str(menor.id),
            menor_id=menor.id,
        )
        raise prohibido("Solo el defensor asignado a este menor puede revocar este permiso")

    repo = PermisoExpedienteRepository(session)
    permiso = repo.por_id(permiso_id)
    if permiso is None or permiso.menor_id != menor.id:
        raise no_encontrado("Permiso no encontrado")
    permiso.activo = False
    permiso = repo.guardar(permiso)
    registrar_acceso(
        session, accion="permiso_revocado", usuario_id=usuario.id, recurso=str(permiso.id), menor_id=menor.id
    )
    return permiso


def revocar_permisos_de_usuario(
    session: Session, menor_id: uuid.UUID, usuario_id: uuid.UUID, actor_id: uuid.UUID | None = None
) -> None:
    """RF7: al cerrar la asignación de la madre, se oculta el expediente (se revocan sus permisos activos)."""
    repo = PermisoExpedienteRepository(session)
    permisos = repo.listar_activos_de_usuario(menor_id, usuario_id)
    if not permisos:
        return
    for permiso in permisos:
        permiso.activo = False
    session.commit()
    registrar_acceso(
        session, accion="permisos_revocados_rf7", usuario_id=actor_id, recurso=str(usuario_id), menor_id=menor_id
    )


def panel_profesional(session: Session, usuario) -> list[ZonaPanelGroup]:
    from app.modules.asignaciones.application import listar_asignaciones
    from app.modules.profesionales.application import menores_asignados_a_profesional, profesional_de_usuario
    from app.modules.zonas_hogares.application import obtener_hogar

    profesional = profesional_de_usuario(session, usuario.id)
    if profesional is None:
        return []

    menor_ids = {mp.menor_id for mp in menores_asignados_a_profesional(session, profesional.id)}
    vigentes = [a for a in listar_asignaciones(session, estado="vigente") if a.menor_id in menor_ids]

    grupos: dict[uuid.UUID, dict[uuid.UUID, list[Menor]]] = {}
    for asignacion in vigentes:
        menor = MenorRepository(session).por_id(asignacion.menor_id)
        if menor is None:
            continue
        hogar = obtener_hogar(session, asignacion.hogar_id)
        grupos.setdefault(hogar.zona_id, {}).setdefault(asignacion.hogar_id, []).append(menor)

    registrar_acceso(session, accion="panel_profesional_consultado", usuario_id=usuario.id)
    return [
        ZonaPanelGroup(zona_id=zona_id, hogares=[HogarPanelGroup(hogar_id=h, menores=ms) for h, ms in hogares.items()])
        for zona_id, hogares in grupos.items()
    ]


def panel_zona(session: Session, usuario) -> list[HogarPanelGroup]:
    """Panel del coordinador: solo datos básicos y asignaciones. Nunca familia/salud/psicosocial (ADR-0007, punto 2)."""
    if usuario.zona_id is None:
        return []

    from app.modules.asignaciones.application import listar_asignaciones

    vigentes = listar_asignaciones(session, zona_id=usuario.zona_id, estado="vigente")

    grupos: dict[uuid.UUID, list[Menor]] = {}
    for asignacion in vigentes:
        menor = MenorRepository(session).por_id(asignacion.menor_id)
        if menor is None:
            continue
        grupos.setdefault(asignacion.hogar_id, []).append(menor)

    registrar_acceso(session, accion="panel_zona_consultado", usuario_id=usuario.id)
    return [HogarPanelGroup(hogar_id=hogar_id, menores=ms) for hogar_id, ms in grupos.items()]
