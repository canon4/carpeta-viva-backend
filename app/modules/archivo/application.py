"""Archivo y Cierre: Casos de uso (ADR-0010, sección 3).

Archiva el expediente cuando el caso del menor se cierra de verdad (sección 3.1) y lo exporta
como paquete verificable (manifest.json + zip cifrado, sección 3.2). A partir de archivar, el
expediente queda de solo lectura: `documentos`/`alertas`/`citas` consultan `esta_archivado`
antes de aceptar escritura (ver sus respectivos `application.py`).

**Corrección obligatoria de seguridad (ADR-0010, revisión de seguridad, "alcance de zona del
coordinador"):** los cuatro endpoints de este módulo acotan `coordinador` a
`usuario.zona_id == zona_id del expediente` (denormalizado en `ExpedienteArchivo.zona_id`, o
resuelto desde la última asignación si el expediente nunca se archivó). `admin` sin restricción;
`auditor` solo metadatos, nunca descarga el paquete (sección 3.5).

Las importaciones de otros módulos se hacen dentro de cada función para evitar ciclos entre
capas de aplicación hermanas (mismo patrón que `documentos`/`menores`/`asignaciones`).
"""
import io
import json
import uuid
import zipfile
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core import almacenamiento
from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido
from app.modules.auth.domain import Rol

from .domain import condicion_archivo_cumplida
from .models import DESTINO_POR_DEFECTO, ExpedienteArchivo
from .repository import ExpedienteArchivoRepository


def _json_default(valor):
    if isinstance(valor, (uuid.UUID,)):
        return str(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return str(valor)


# ---------------------------------------------------------------------------
# Resolución de zona y autorización
# ---------------------------------------------------------------------------

def _zona_de_menor(session: Session, menor_id: uuid.UUID) -> uuid.UUID | None:
    """Zona del hogar de la asignación vigente, o de la última asignación cerrada si ya no hay
    vigente (que es, precisamente, el caso que dispara el archivo, ADR-0010 sección 3.1)."""
    from app.modules.asignaciones.application import listar_asignaciones
    from app.modules.zonas_hogares.application import obtener_hogar

    asignaciones = listar_asignaciones(session, menor_id=menor_id)
    if not asignaciones:
        return None
    ultima = asignaciones[-1]  # `listar_asignaciones` ordena por fecha_inicio ascendente
    hogar = obtener_hogar(session, ultima.hogar_id)
    return hogar.zona_id


def obtener_zona_archivo(session: Session, menor_id: uuid.UUID) -> uuid.UUID | None:
    """Zona "oficial" del expediente para efectos de autorización: la denormalizada en
    `expedientes_archivo` si ya existe una fila, o la resuelta desde la asignación si todavía no
    se archivó (necesaria para autorizar el propio `POST /cerrar`, que crea esa fila)."""
    expediente = ExpedienteArchivoRepository(session).por_menor(menor_id)
    if expediente is not None and expediente.zona_id is not None:
        return expediente.zona_id
    return _zona_de_menor(session, menor_id)


def _coordinador_de_zona(usuario, zona_id: uuid.UUID | None) -> bool:
    return usuario.zona_id is not None and zona_id is not None and usuario.zona_id == zona_id


def _autorizado_cerrar_o_consultar(session: Session, usuario, menor_id: uuid.UUID) -> bool:
    """Autorización común a `cerrar_expediente`/`obtener_estado` (ADR-0010, corrección de
    seguridad: mismo criterio para los dos, acotado a zona para coordinador)."""
    rol = usuario.rol
    if rol == Rol.ADMIN.value:
        return True
    if rol == Rol.AUDITOR.value:
        return True
    if rol == Rol.COORDINADOR.value:
        return _coordinador_de_zona(usuario, obtener_zona_archivo(session, menor_id))
    return False


def _autorizado_paquete(session: Session, usuario, menor_id: uuid.UUID) -> bool:
    """`GET /archivo/menores/{id}/paquete`: auditor nunca descarga (ADR-0010, sección 3.5)."""
    rol = usuario.rol
    if rol == Rol.AUDITOR.value:
        return False
    if rol == Rol.ADMIN.value:
        return True
    if rol == Rol.COORDINADOR.value:
        return _coordinador_de_zona(usuario, obtener_zona_archivo(session, menor_id))
    return False


def autorizado_para_ver_archivado(session: Session, usuario, menor_id: uuid.UUID) -> bool:
    """Wrapper público: usado por `reportes.application` para la revalidación obligatoria al
    descargar un informe exportado cuyo menor haya sido archivado después de generarse (ADR-0010,
    sección 2, corrección de seguridad). Mismo criterio que `obtener_estado` (no el de
    `/paquete`, que excluye auditor): un reporte agregado/metadatos no es el paquete binario."""
    return _autorizado_cerrar_o_consultar(session, usuario, menor_id)


# ---------------------------------------------------------------------------
# Estado de archivo (consultado por otros módulos para bloquear escritura)
# ---------------------------------------------------------------------------

def esta_archivado(session: Session, menor_id: uuid.UUID) -> bool:
    """Sin control de autorización: lo consultan `documentos`/`alertas`/`citas` antes de aceptar
    una escritura nueva sobre ese menor (ADR-0010, sección 3.2, corrección obligatoria)."""
    expediente = ExpedienteArchivoRepository(session).por_menor(menor_id)
    return expediente is not None and expediente.estado == "archivado"


# ---------------------------------------------------------------------------
# Manifiesto y paquete verificable
# ---------------------------------------------------------------------------

def _construir_manifiesto(session: Session, menor_id: uuid.UUID) -> dict:
    from app.modules.asignaciones.application import historial_asignacion_interno, listar_asignaciones
    from app.modules.citas.application import listar_citas_interno
    from app.modules.documentos.application import (
        listar_documentos_interno,
        listar_reportes_interno,
        listar_versiones_interno,
    )
    from app.modules.alertas.application import listar_alertas_interno
    from app.modules.menores.application import historial_menor_interno, menor_por_id_interno, permisos_interno

    menor = menor_por_id_interno(session, menor_id)

    documentos = []
    for documento in listar_documentos_interno(session, menor_id):
        versiones = [
            {
                "version": v.version,
                "hash_sha256": v.hash_sha256,
                "estado_flujo": v.estado_flujo,
                "created_at": v.created_at,
            }
            for v in listar_versiones_interno(session, documento.id)
        ]
        documentos.append(
            {
                "id": documento.id,
                "categoria": documento.categoria,
                "titulo": documento.titulo,
                "estado_flujo": documento.estado_flujo,
                "version_vigente": documento.version,
                "hash_sha256_vigente": documento.hash_sha256,
                "sensible": documento.sensible,
                "versiones_anteriores": versiones,
            }
        )

    reportes = [
        {
            "id": r.id,
            "tipo_reporte": r.tipo_reporte,
            "version": r.version,
            "hash_contenido": almacenamiento.calcular_hash(
                json.dumps(r.contenido, sort_keys=True, default=_json_default).encode("utf-8")
            ),
            "created_at": r.created_at,
        }
        for r in listar_reportes_interno(session, menor_id)
    ]

    menores_history = [
        {
            "version": h.version,
            "estado_actual": h.estado_actual,
            "motivo": h.motivo,
            "cambiado_por": h.cambiado_por,
            "created_at": h.created_at,
        }
        for h in historial_menor_interno(session, menor_id)
    ]

    asignaciones_out = []
    for asignacion in listar_asignaciones(session, menor_id=menor_id):
        historial = [
            {
                "version": h.version,
                "hogar_id": h.hogar_id,
                "fecha_inicio": h.fecha_inicio,
                "fecha_fin": h.fecha_fin,
                "estado": h.estado,
                "tipo_movimiento": h.tipo_movimiento,
                "created_at": h.created_at,
            }
            for h in historial_asignacion_interno(session, asignacion.id)
        ]
        asignaciones_out.append(
            {
                "id": asignacion.id,
                "hogar_id": asignacion.hogar_id,
                "fecha_inicio": asignacion.fecha_inicio,
                "fecha_fin": asignacion.fecha_fin,
                "estado": asignacion.estado,
                "tipo_movimiento": asignacion.tipo_movimiento,
                "acta_referencia": asignacion.acta_referencia,
                "historial": historial,
            }
        )

    permisos = [
        {
            "seccion": p.seccion,
            "usuario_id": p.usuario_id,
            "otorgado_por": p.otorgado_por,
            "activo": p.activo,
            "created_at": p.created_at,
        }
        for p in permisos_interno(session, menor_id)
    ]

    alertas = [
        {"id": a.id, "tipo": a.tipo, "estado": a.estado, "origen": a.origen, "created_at": a.created_at}
        for a in listar_alertas_interno(session, menor_id)
    ]

    citas = [
        {"id": c.id, "tipo": c.tipo, "estado": c.estado, "fecha_hora": c.fecha_hora}
        for c in listar_citas_interno(session, menor_id)
    ]

    return {
        "menor_id": menor.id,
        "estado_actual_al_cerrar": menor.estado_actual,
        "generado_en": datetime.now(timezone.utc),
        "documentos": documentos,
        "reportes": reportes,
        "menores_history": menores_history,
        "asignaciones": asignaciones_out,
        "permisos_expediente": permisos,
        "alertas": alertas,
        "citas": citas,
    }


def _construir_paquete_zip(session: Session, menor_id: uuid.UUID, manifiesto: dict, manifiesto_bytes: bytes) -> bytes:
    """Zip en memoria (sin cifrar aún) con `manifest.json` + el contenido descifrado de cada
    documento vigente que tenga archivo asociado. El zip completo se cifra después con
    `app/core/almacenamiento.py` (ADR-0010, sección 3.2: "sin reinventar cifrado nuevo")."""
    from app.modules.documentos.application import listar_documentos_interno

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifiesto_bytes)
        for documento in listar_documentos_interno(session, menor_id):
            if documento.referencia_archivo is None:
                continue
            try:
                contenido = almacenamiento.leer(documento.referencia_archivo, documento.hash_sha256)
            except FileNotFoundError:
                # Documento de migración/registro sin archivo físico asociado en este entorno
                # (p. ej. datos sintéticos de prueba): el manifiesto ya deja constancia del hash
                # esperado; no se bloquea el cierre por un archivo faltante en disco.
                continue
            nombre = f"documentos/{documento.id}/v{documento.version}/{documento.nombre_original}"
            zf.writestr(nombre, contenido)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Casos de uso públicos
# ---------------------------------------------------------------------------

def cerrar_expediente(session: Session, usuario, menor_id: uuid.UUID, motivo: str) -> ExpedienteArchivo:
    from app.modules.asignaciones.application import vigente_de_menor
    from app.modules.menores.application import menor_por_id_interno

    zona_id = obtener_zona_archivo(session, menor_id)
    if not _autorizado_cerrar_o_consultar(session, usuario, menor_id) or usuario.rol == Rol.AUDITOR.value:
        registrar_acceso(
            session, accion="expediente_cierre_denegado", usuario_id=usuario.id, menor_id=menor_id
        )
        raise prohibido()

    repo = ExpedienteArchivoRepository(session)
    expediente = repo.por_menor(menor_id)
    if expediente is not None and expediente.estado == "archivado":
        raise ValueError("El expediente ya está archivado")

    menor = menor_por_id_interno(session, menor_id)
    vigente = vigente_de_menor(session, menor_id)
    if not condicion_archivo_cumplida(menor.estado_actual, vigente is not None):
        raise ValueError(
            "El expediente no cumple la condición de cierre: el menor debe estar egresado o "
            "fallecido y sin ninguna asignación vigente"
        )

    manifiesto = _construir_manifiesto(session, menor_id)
    manifiesto_bytes = json.dumps(manifiesto, sort_keys=True, default=_json_default, ensure_ascii=False).encode(
        "utf-8"
    )
    manifiesto_hash = almacenamiento.calcular_hash(manifiesto_bytes)
    paquete_bytes = _construir_paquete_zip(session, menor_id, manifiesto, manifiesto_bytes)

    if expediente is None:
        expediente = ExpedienteArchivo(menor_id=menor_id, estado="activo", destino=DESTINO_POR_DEFECTO)
        expediente = repo.crear(expediente)

    referencia, _hash_zip = almacenamiento.guardar(menor_id, expediente.id, 1, paquete_bytes)

    expediente.estado = "archivado"
    expediente.archivado_en = datetime.now(timezone.utc)
    expediente.archivado_por = usuario.id
    expediente.motivo = motivo
    expediente.zona_id = zona_id
    expediente.paquete_referencia = referencia
    expediente.paquete_hash = manifiesto_hash
    expediente = repo.guardar(expediente)

    registrar_acceso(
        session, accion="expediente_archivado", usuario_id=usuario.id, recurso=str(expediente.id), menor_id=menor_id
    )
    return expediente


def obtener_estado(session: Session, usuario, menor_id: uuid.UUID) -> ExpedienteArchivo:
    if not _autorizado_cerrar_o_consultar(session, usuario, menor_id):
        registrar_acceso(
            session, accion="expediente_estado_denegado", usuario_id=usuario.id, menor_id=menor_id
        )
        raise prohibido()

    expediente = ExpedienteArchivoRepository(session).por_menor(menor_id)
    if expediente is None:
        expediente = ExpedienteArchivo(menor_id=menor_id, estado="activo", destino=DESTINO_POR_DEFECTO)

    registrar_acceso(
        session, accion="expediente_estado_consultado", usuario_id=usuario.id, menor_id=menor_id
    )
    return expediente


def obtener_paquete(session: Session, usuario, menor_id: uuid.UUID) -> tuple[ExpedienteArchivo, bytes]:
    if not _autorizado_paquete(session, usuario, menor_id):
        registrar_acceso(
            session, accion="expediente_paquete_denegado", usuario_id=usuario.id, menor_id=menor_id
        )
        raise prohibido()

    expediente = ExpedienteArchivoRepository(session).por_menor(menor_id)
    if expediente is None or expediente.estado != "archivado" or expediente.paquete_referencia is None:
        raise no_encontrado("El expediente de este menor no está archivado")

    contenido = almacenamiento.leer(expediente.paquete_referencia)
    registrar_acceso(
        session, accion="expediente_paquete_descargado", usuario_id=usuario.id, recurso=str(expediente.id), menor_id=menor_id
    )
    return expediente, contenido


def listar_archivados(
    session: Session,
    usuario,
    zona_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> list[ExpedienteArchivo]:
    """ADR-0010, sección 3.5: coordinador de su zona, admin. (Sin mención de auditor en este
    listado; se deniega por defecto, a diferencia de los otros tres endpoints del módulo.)"""
    rol = usuario.rol
    if rol == Rol.ADMIN.value:
        resultado = ExpedienteArchivoRepository(session).listar_archivados(zona_id=zona_id, desde=desde, hasta=hasta)
    elif rol == Rol.COORDINADOR.value:
        if usuario.zona_id is None:
            resultado = []
        elif zona_id is not None and zona_id != usuario.zona_id:
            registrar_acceso(session, accion="expedientes_listado_denegado", usuario_id=usuario.id)
            raise prohibido()
        else:
            resultado = ExpedienteArchivoRepository(session).listar_archivados(
                zona_id=usuario.zona_id, desde=desde, hasta=hasta
            )
    else:
        registrar_acceso(session, accion="expedientes_listado_denegado", usuario_id=usuario.id)
        raise prohibido()

    registrar_acceso(session, accion="expedientes_listados", usuario_id=usuario.id)
    return resultado
