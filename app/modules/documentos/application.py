"""Gestión Documental: Casos de uso.

Carga, clasificación, versionado y flujo de revisión: la madre crea, el profesional revisa y
aprueba o devuelve. Ver docs/adr/0008-gestion-documental-almacenamiento-cifrado-y-flujo.md.

Las importaciones de otros módulos (`menores`, `profesionales`, `madres`, `zonas_hogares`) se
hacen dentro de cada función para evitar ciclos de importación entre capas de aplicación
hermanas, igual que en `menores`/`asignaciones`.
"""
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core import almacenamiento
from app.core.audit import registrar_acceso
from app.core.compresion import comprimir_si_es_imagen
from app.core.config import get_settings
from app.core.errors import no_encontrado, prohibido
from app.modules.auth.domain import Rol

from .domain import es_visualizable, seccion_de_categoria, seccion_de_tipo_reporte
from .models import Documento, DocumentoVersion, Reporte
from .repository import DocumentoRepository, DocumentoVersionRepository, ReporteRepository
from .schemas import ReporteCreate


def _validar_tamanio(contenido: bytes) -> None:
    """Límite de tamaño por archivo (RF2), para que un usuario autenticado no pueda llenar el
    disco subiendo archivos repetidamente. Config: `ARCHIVOS_TAMANIO_MAXIMO_BYTES`."""
    maximo = get_settings().archivos_tamanio_maximo_bytes
    if len(contenido) > maximo:
        raise ValueError(f"El archivo supera el tamaño máximo permitido ({maximo // (1024 * 1024)} MB)")
    if len(contenido) == 0:
        raise ValueError("El archivo está vacío")


def _documento_o_404(session: Session, documento_id: uuid.UUID) -> Documento:
    documento = DocumentoRepository(session).por_id(documento_id)
    if documento is None:
        raise no_encontrado("Documento no encontrado")
    return documento


def _programar_indexacion_documento(
    tareas_fondo: BackgroundTasks | None, session: Session, documento_id: uuid.UUID
) -> None:
    """Hookea la indexación de IA (OCR + clasificación + embeddings, ADR-0010 sección 1.3) tras
    guardar un documento o una nueva versión. `documentos` llama a `ia.application`, nunca al
    revés (ADR-0010: "no hagas que ia dependa de documentos en sentido inverso"). Import
    diferido, mismo patrón que el resto del módulo; `tareas_fondo` es opcional para no romper
    llamadas internas/pruebas que no vienen de un endpoint HTTP. Se reutiliza la misma `session`
    de la petición: en Starlette/FastAPI las tareas de `BackgroundTasks` corren antes de que la
    dependencia `Depends(get_session)` cierre la sesión (verificado empíricamente), así que
    sigue abierta y, en pruebas, sigue apuntando al motor SQLite aislado de esa prueba."""
    if tareas_fondo is None or not get_settings().ia_indexar_automaticamente:
        return
    from app.modules.ia.application import indexar_documento_en_segundo_plano

    tareas_fondo.add_task(indexar_documento_en_segundo_plano, session, documento_id)


def _programar_indexacion_reporte(tareas_fondo: BackgroundTasks | None, session: Session, reporte_id: uuid.UUID) -> None:
    if tareas_fondo is None or not get_settings().ia_indexar_automaticamente:
        return
    from app.modules.ia.application import indexar_reporte_en_segundo_plano

    tareas_fondo.add_task(indexar_reporte_en_segundo_plano, session, reporte_id)


# ---------------------------------------------------------------------------
# Autorización
# ---------------------------------------------------------------------------

def _puede_ver_documento_hogar(session: Session, usuario, hogar_id: uuid.UUID) -> bool:
    """ADR-0008, sección 2.1: documentos de hogar (p. ej. `madre_habilitacion`)."""
    from app.modules.zonas_hogares.application import obtener_hogar

    rol = usuario.rol
    if rol in (Rol.ADMIN.value, Rol.AUDITOR.value):
        return True
    if rol == Rol.COORDINADOR.value:
        if usuario.zona_id is None:
            return False
        hogar = obtener_hogar(session, hogar_id)
        return hogar.zona_id == usuario.zona_id
    if rol == Rol.MADRE.value:
        from app.modules.madres.application import madre_de_usuario

        madre = madre_de_usuario(session, usuario.id)
        if madre is None:
            return False
        hogar = obtener_hogar(session, hogar_id)
        return hogar.madre_id == madre.id
    return False


def _puede_ver_documento(session: Session, usuario, documento: Documento) -> bool:
    """Regla de autorización de lectura (ADR-0008, sección 4)."""
    if documento.menor_id is None and documento.hogar_id is not None:
        return _puede_ver_documento_hogar(session, usuario, documento.hogar_id)

    if documento.menor_id is None:
        return False

    from app.modules.menores.application import puede_ver_menor, tiene_permiso_seccion

    seccion = seccion_de_categoria(session, documento.categoria)
    if seccion is None:
        return puede_ver_menor(session, usuario, documento.menor_id)
    return tiene_permiso_seccion(session, usuario, documento.menor_id, seccion)


def _puede_descargar_contenido(session: Session, usuario, documento: Documento) -> bool:
    """Corrección obligatoria de seguridad (ADR-0008, sección 4/6): el auditor nunca accede a
    contenido descifrado, sin importar la categoría."""
    if usuario.rol == Rol.AUDITOR.value:
        return False
    return _puede_ver_documento(session, usuario, documento)


def _resolver_creacion_menor(session: Session, usuario, menor_id: uuid.UUID, categoria: str, migracion: bool) -> str | None:
    """Devuelve el estado_flujo inicial si el usuario puede crear el documento, o `None` si no."""
    from app.modules.menores.application import puede_ver_menor, tiene_permiso_seccion
    from app.modules.profesionales.application import esta_asignado_a_menor, profesional_de_usuario

    rol = usuario.rol

    if rol in (Rol.COORDINADOR.value, Rol.ADMIN.value) and migracion:
        return "aprobado"

    if rol in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        profesional = profesional_de_usuario(session, usuario.id)
        if profesional is not None and esta_asignado_a_menor(session, profesional.id, menor_id):
            return "aprobado"
        return None

    if rol == Rol.MADRE.value:
        if not puede_ver_menor(session, usuario, menor_id):
            return None
        seccion = seccion_de_categoria(session, categoria)
        if seccion is not None and not tiene_permiso_seccion(session, usuario, menor_id, seccion):
            return None
        return "borrador"

    return None


def _resolver_creacion_hogar(session: Session, usuario, hogar_id: uuid.UUID, categoria: str) -> str | None:
    from app.modules.configuracion.application import valor_valido_en_catalogo
    from app.modules.zonas_hogares.application import obtener_hogar

    if not valor_valido_en_catalogo(session, "categoria_documento_hogar", categoria):
        return None
    rol = usuario.rol
    if rol == Rol.ADMIN.value:
        return "aprobado"
    if rol == Rol.COORDINADOR.value:
        if usuario.zona_id is None:
            return None
        hogar = obtener_hogar(session, hogar_id)
        return "aprobado" if hogar.zona_id == usuario.zona_id else None
    if rol == Rol.MADRE.value:
        from app.modules.madres.application import madre_de_usuario

        madre = madre_de_usuario(session, usuario.id)
        if madre is None:
            return None
        hogar = obtener_hogar(session, hogar_id)
        return "borrador" if hogar.madre_id == madre.id else None
    return None


def _puede_editar_documento(session: Session, usuario, documento: Documento) -> bool:
    """Autorización para enviar/versionar: el creador, o quien tendría el mismo permiso de
    creación sobre ese menor/hogar y categoría (p. ej. reemplazo del profesional asignado)."""
    if usuario.id == documento.creado_por:
        return True
    if documento.menor_id is not None:
        return _resolver_creacion_menor(session, usuario, documento.menor_id, documento.categoria, migracion=False) is not None
    if documento.hogar_id is not None:
        return _resolver_creacion_hogar(session, usuario, documento.hogar_id, documento.categoria) is not None
    return False


def _puede_revisar(session: Session, usuario, documento: Documento) -> bool:
    """Aprobar/devolver: cualquier profesional/defensor asignado al menor (ADR-0008, sección 3)."""
    if documento.menor_id is None:
        return False
    from app.modules.profesionales.application import esta_asignado_a_menor, profesional_de_usuario

    if usuario.rol not in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        return False
    profesional = profesional_de_usuario(session, usuario.id)
    return profesional is not None and esta_asignado_a_menor(session, profesional.id, documento.menor_id)


# ---------------------------------------------------------------------------
# Documentos
# ---------------------------------------------------------------------------

def crear_documento(
    session: Session,
    usuario,
    *,
    menor_id: uuid.UUID | None,
    hogar_id: uuid.UUID | None,
    categoria: str,
    titulo: str,
    contenido: bytes,
    nombre_original: str,
    mime_type: str,
    migracion: bool = False,
    motivo: str | None = None,
    tareas_fondo: BackgroundTasks | None = None,
) -> Documento:
    if (menor_id is None) == (hogar_id is None):
        raise ValueError("Debe indicarse exactamente uno de menor_id o hogar_id")
    if migracion and usuario.rol in (Rol.COORDINADOR.value, Rol.ADMIN.value) and not motivo:
        raise ValueError("motivo es obligatorio para documentos de migración histórica")
    if esta_archivado(session, menor_id):
        registrar_acceso(
            session, accion="documento_creacion_denegada_archivado", usuario_id=usuario.id, menor_id=menor_id
        )
        raise prohibido("El expediente está archivado; no se pueden crear documentos nuevos")

    from app.modules.configuracion.application import valor_valido_en_catalogo

    grupo_categoria = "categoria_documento_menor" if menor_id is not None else "categoria_documento_hogar"
    if not valor_valido_en_catalogo(session, grupo_categoria, categoria):
        raise ValueError(f"Categoría desconocida: {categoria}")

    if menor_id is not None:
        estado_inicial = _resolver_creacion_menor(session, usuario, menor_id, categoria, migracion)
    else:
        estado_inicial = _resolver_creacion_hogar(session, usuario, hogar_id, categoria)

    if estado_inicial is None:
        registrar_acceso(
            session, accion="documento_creacion_denegada", usuario_id=usuario.id, menor_id=menor_id
        )
        raise prohibido()

    _validar_tamanio(contenido)

    documento = Documento(
        menor_id=menor_id,
        hogar_id=hogar_id,
        categoria=categoria,
        titulo=titulo,
        estado_flujo=estado_inicial,
        version=1,
        sensible=seccion_de_categoria(session, categoria) is not None,
        creado_por=usuario.id,
        nombre_original=nombre_original,
        mime_type=mime_type,
        tamanio_bytes=len(contenido),
    )
    documento = DocumentoRepository(session).crear(documento)

    propietario_id = menor_id if menor_id is not None else hogar_id
    referencia, hash_sha256 = almacenamiento.guardar(propietario_id, documento.id, documento.version, contenido)
    documento.referencia_archivo = referencia
    documento.hash_sha256 = hash_sha256
    documento = DocumentoRepository(session).guardar(documento)

    registrar_acceso(
        session, accion="documento_creado", usuario_id=usuario.id, recurso=str(documento.id), menor_id=menor_id
    )
    _programar_indexacion_documento(tareas_fondo, session, documento.id)
    return documento


def listar_documentos(
    session: Session,
    usuario,
    menor_id: uuid.UUID | None = None,
    hogar_id: uuid.UUID | None = None,
    categoria: str | None = None,
    estado_flujo: str | None = None,
) -> list[Documento]:
    crudo = DocumentoRepository(session).listar(
        menor_id=menor_id, hogar_id=hogar_id, categoria=categoria, estado_flujo=estado_flujo
    )
    resultado = [d for d in crudo if _puede_ver_documento(session, usuario, d)]
    registrar_acceso(session, accion="documentos_listados", usuario_id=usuario.id)
    return resultado


def obtener_documento(session: Session, usuario, documento_id: uuid.UUID) -> Documento:
    documento = _documento_o_404(session, documento_id)
    if not _puede_ver_documento(session, usuario, documento):
        registrar_acceso(
            session,
            accion="documento_consulta_denegada",
            usuario_id=usuario.id,
            recurso=str(documento.id),
            menor_id=documento.menor_id,
        )
        raise prohibido()
    registrar_acceso(
        session, accion="documento_consultado", usuario_id=usuario.id, recurso=str(documento.id), menor_id=documento.menor_id
    )
    return documento


def descargar_documento(session: Session, usuario, documento_id: uuid.UUID) -> tuple[Documento, bytes]:
    documento = _documento_o_404(session, documento_id)
    if not _puede_descargar_contenido(session, usuario, documento):
        registrar_acceso(
            session,
            accion="documento_descarga_denegada",
            usuario_id=usuario.id,
            recurso=str(documento.id),
            menor_id=documento.menor_id,
        )
        raise prohibido()
    contenido = almacenamiento.leer(documento.referencia_archivo, documento.hash_sha256)
    registrar_acceso(
        session, accion="documento_descargado", usuario_id=usuario.id, recurso=str(documento.id), menor_id=documento.menor_id
    )
    return documento, contenido


def visualizar_documento(session: Session, usuario, documento_id: uuid.UUID) -> tuple[Documento, bytes]:
    """Visor en pantalla (ADR-0011): misma autorización que `descargar_documento` (nunca el
    auditor), pero solo para tipos que el navegador puede mostrar sin descargar (`es_visualizable`).
    Para los demás formatos (Word/Excel, etc.) no hay visor; se usa la descarga existente."""
    documento = _documento_o_404(session, documento_id)
    if not es_visualizable(documento.mime_type):
        raise ValueError("Este tipo de archivo no se puede previsualizar; descárguelo para verlo")
    if not _puede_descargar_contenido(session, usuario, documento):
        registrar_acceso(
            session,
            accion="documento_visualizacion_denegada",
            usuario_id=usuario.id,
            recurso=str(documento.id),
            menor_id=documento.menor_id,
        )
        raise prohibido()
    contenido = almacenamiento.leer(documento.referencia_archivo, documento.hash_sha256)
    registrar_acceso(
        session, accion="documento_visualizado", usuario_id=usuario.id, recurso=str(documento.id), menor_id=documento.menor_id
    )
    return documento, contenido


def enviar_documento(session: Session, usuario, documento_id: uuid.UUID) -> Documento:
    documento = _documento_o_404(session, documento_id)
    if documento.estado_flujo != "borrador":
        raise ValueError("Solo un documento en borrador puede enviarse a revisión")
    if not _puede_editar_documento(session, usuario, documento):
        registrar_acceso(
            session,
            accion="documento_envio_denegado",
            usuario_id=usuario.id,
            recurso=str(documento.id),
            menor_id=documento.menor_id,
        )
        raise prohibido()
    documento.estado_flujo = "en_revision"
    documento = DocumentoRepository(session).guardar(documento)
    registrar_acceso(
        session, accion="documento_enviado", usuario_id=usuario.id, recurso=str(documento.id), menor_id=documento.menor_id
    )
    return documento


def aprobar_documento(session: Session, usuario, documento_id: uuid.UUID) -> Documento:
    documento = _documento_o_404(session, documento_id)
    if documento.estado_flujo != "en_revision":
        raise ValueError("Solo un documento en revisión puede aprobarse")
    if not _puede_revisar(session, usuario, documento):
        registrar_acceso(
            session,
            accion="documento_aprobacion_denegada",
            usuario_id=usuario.id,
            recurso=str(documento.id),
            menor_id=documento.menor_id,
        )
        raise prohibido()
    documento.estado_flujo = "aprobado"
    documento.revisado_por = usuario.id
    documento.revisado_en = datetime.now(timezone.utc)
    documento = DocumentoRepository(session).guardar(documento)
    registrar_acceso(
        session, accion="documento_aprobado", usuario_id=usuario.id, recurso=str(documento.id), menor_id=documento.menor_id
    )
    return documento


def devolver_documento(session: Session, usuario, documento_id: uuid.UUID, motivo: str) -> Documento:
    documento = _documento_o_404(session, documento_id)
    if documento.estado_flujo != "en_revision":
        raise ValueError("Solo un documento en revisión puede devolverse")
    if not _puede_revisar(session, usuario, documento):
        registrar_acceso(
            session,
            accion="documento_devolucion_denegada",
            usuario_id=usuario.id,
            recurso=str(documento.id),
            menor_id=documento.menor_id,
        )
        raise prohibido()
    documento.estado_flujo = "devuelto"
    documento.revisado_por = usuario.id
    documento.revisado_en = datetime.now(timezone.utc)
    documento.motivo_devolucion = motivo
    documento = DocumentoRepository(session).guardar(documento)
    registrar_acceso(
        session, accion="documento_devuelto", usuario_id=usuario.id, recurso=str(documento.id), menor_id=documento.menor_id
    )
    return documento


def crear_version(
    session: Session,
    usuario,
    documento_id: uuid.UUID,
    *,
    contenido: bytes,
    nombre_original: str,
    mime_type: str,
    tareas_fondo: BackgroundTasks | None = None,
) -> Documento:
    documento = _documento_o_404(session, documento_id)
    if documento.estado_flujo not in ("borrador", "devuelto"):
        raise ValueError("Solo se puede subir una nueva versión en estado borrador o devuelto")
    if esta_archivado(session, documento.menor_id):
        registrar_acceso(
            session,
            accion="documento_version_denegada_archivado",
            usuario_id=usuario.id,
            recurso=str(documento.id),
            menor_id=documento.menor_id,
        )
        raise prohibido("El expediente está archivado; no se pueden crear versiones nuevas")
    if not _puede_editar_documento(session, usuario, documento):
        registrar_acceso(
            session,
            accion="documento_version_denegada",
            usuario_id=usuario.id,
            recurso=str(documento.id),
            menor_id=documento.menor_id,
        )
        raise prohibido()
    _validar_tamanio(contenido)

    # ADR-0011: la versión que queda reemplazada solo sirve como registro histórico, nunca vuelve
    # a ser el archivo vigente; si es una imagen se guarda comprimida (misma ruta, se sobrescribe
    # en el disco) para no acumular espacio con versiones viejas. PDF y otros formatos se
    # conservan tal cual (comprensión de documento_version con comprimida=False).
    hash_version = documento.hash_sha256
    mime_version = documento.mime_type
    tamanio_version = documento.tamanio_bytes
    comprimida = False
    if documento.referencia_archivo is not None:
        contenido_anterior = almacenamiento.leer(documento.referencia_archivo, documento.hash_sha256)
        comprimido, mime_comprimido, fue_comprimida = comprimir_si_es_imagen(contenido_anterior, documento.mime_type)
        if fue_comprimida:
            hash_version = almacenamiento.sobrescribir(documento.referencia_archivo, comprimido)
            mime_version = mime_comprimido
            tamanio_version = len(comprimido)
            comprimida = True

    snapshot = DocumentoVersion(
        documento_id=documento.id,
        version=documento.version,
        referencia_archivo=documento.referencia_archivo,
        hash_sha256=hash_version,
        nombre_original=documento.nombre_original,
        mime_type=mime_version,
        tamanio_bytes=tamanio_version,
        estado_flujo=documento.estado_flujo,
        creado_por=documento.creado_por,
        revisado_por=documento.revisado_por,
        motivo_devolucion=documento.motivo_devolucion,
        comprimida=comprimida,
    )
    DocumentoVersionRepository(session).crear(snapshot)

    documento.version += 1
    documento.estado_flujo = "en_revision"
    documento.nombre_original = nombre_original
    documento.mime_type = mime_type
    documento.tamanio_bytes = len(contenido)
    documento.motivo_devolucion = None

    propietario_id = documento.menor_id if documento.menor_id is not None else documento.hogar_id
    referencia, hash_sha256 = almacenamiento.guardar(propietario_id, documento.id, documento.version, contenido)
    documento.referencia_archivo = referencia
    documento.hash_sha256 = hash_sha256
    documento = DocumentoRepository(session).guardar(documento)

    registrar_acceso(
        session, accion="documento_version_creada", usuario_id=usuario.id, recurso=str(documento.id), menor_id=documento.menor_id
    )
    _programar_indexacion_documento(tareas_fondo, session, documento.id)
    return documento


def listar_versiones(session: Session, usuario, documento_id: uuid.UUID) -> list[DocumentoVersion]:
    documento = _documento_o_404(session, documento_id)
    if not _puede_ver_documento(session, usuario, documento):
        registrar_acceso(
            session,
            accion="documento_versiones_denegadas",
            usuario_id=usuario.id,
            recurso=str(documento.id),
            menor_id=documento.menor_id,
        )
        raise prohibido()
    registrar_acceso(
        session, accion="documento_versiones_consultadas", usuario_id=usuario.id, recurso=str(documento.id), menor_id=documento.menor_id
    )
    return DocumentoVersionRepository(session).listar_por_documento(documento.id)


def descargar_version(session: Session, usuario, documento_id: uuid.UUID, version: int) -> tuple[DocumentoVersion, bytes]:
    documento = _documento_o_404(session, documento_id)
    version_obj = DocumentoVersionRepository(session).por_documento_y_version(documento.id, version)
    if version_obj is None:
        raise no_encontrado("Versión no encontrada")
    if not _puede_descargar_contenido(session, usuario, documento):
        registrar_acceso(
            session,
            accion="documento_version_descarga_denegada",
            usuario_id=usuario.id,
            recurso=str(documento.id),
            menor_id=documento.menor_id,
        )
        raise prohibido()
    if version_obj.referencia_archivo is None:
        raise no_encontrado("Versión sin archivo asociado")
    contenido = almacenamiento.leer(version_obj.referencia_archivo, version_obj.hash_sha256)
    registrar_acceso(
        session,
        accion="documento_version_descargada",
        usuario_id=usuario.id,
        recurso=str(documento.id),
        menor_id=documento.menor_id,
    )
    return version_obj, contenido


def listar_documentos_interno(session: Session, menor_id: uuid.UUID) -> list[Documento]:
    """Uso interno (sin control de autorización) para el manifiesto del paquete de archivo
    (ADR-0010, sección 3.2): incluye documentos de todas las categorías, incluidas las
    sensibles que un coordinador no vería con `listar_documentos` normal. El llamador
    (`archivo.application`) ya validó que quien cierra el expediente es coordinador de la
    zona del expediente o admin. No exponer en `api.py`."""
    return DocumentoRepository(session).listar(menor_id=menor_id)


def listar_versiones_interno(session: Session, documento_id: uuid.UUID) -> list[DocumentoVersion]:
    """Uso interno (sin control de autorización), mismo caso que `listar_documentos_interno`."""
    return DocumentoVersionRepository(session).listar_por_documento(documento_id)


def listar_reportes_interno(session: Session, menor_id: uuid.UUID) -> list[Reporte]:
    """Uso interno (sin control de autorización), mismo caso que `listar_documentos_interno`."""
    return ReporteRepository(session).listar(menor_id=menor_id)


def esta_archivado(session: Session, menor_id: uuid.UUID | None) -> bool:
    """Corrección obligatoria (ADR-0010, sección 3.2): ningún rol puede crear documentos nuevos
    para un menor cuyo expediente ya está archivado. Import diferido para evitar un ciclo entre
    `documentos`/`archivo` (mismo patrón que el resto del módulo)."""
    if menor_id is None:
        return False
    from app.modules.archivo.application import esta_archivado as _esta_archivado_archivo

    return _esta_archivado_archivo(session, menor_id)


def listar_para_auditor(session: Session, usuario) -> list[Documento]:
    """GET /documentos/auditor: metadatos de todos los documentos no sensibles, nunca contenido
    (ADR-0007 punto 3, ADR-0008 sección 6)."""
    if usuario.rol != Rol.AUDITOR.value:
        registrar_acceso(session, accion="documentos_auditor_denegado", usuario_id=usuario.id)
        raise prohibido()
    documentos = [d for d in DocumentoRepository(session).listar() if not d.sensible]
    registrar_acceso(session, accion="documentos_auditor_consultados", usuario_id=usuario.id)
    return documentos


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------

def crear_reporte(
    session: Session, usuario, datos: ReporteCreate, *, tareas_fondo: BackgroundTasks | None = None
) -> Reporte:
    from app.modules.profesionales.application import esta_asignado_a_menor, profesional_de_usuario

    if usuario.rol not in (Rol.PROFESIONAL.value, Rol.DEFENSOR.value):
        registrar_acceso(session, accion="reporte_creacion_denegada", usuario_id=usuario.id, menor_id=datos.menor_id)
        raise prohibido()
    if esta_archivado(session, datos.menor_id):
        registrar_acceso(
            session, accion="reporte_creacion_denegada_archivado", usuario_id=usuario.id, menor_id=datos.menor_id
        )
        raise prohibido("El expediente está archivado; no se pueden crear reportes nuevos")
    profesional = profesional_de_usuario(session, usuario.id)
    if profesional is None or not esta_asignado_a_menor(session, profesional.id, datos.menor_id):
        registrar_acceso(session, accion="reporte_creacion_denegada", usuario_id=usuario.id, menor_id=datos.menor_id)
        raise prohibido()

    reporte = Reporte(
        menor_id=datos.menor_id,
        autor_id=usuario.id,
        tipo_autor=usuario.rol,
        tipo_reporte=datos.tipo_reporte,
        contenido=datos.contenido,
        referencia_archivo=datos.referencia_archivo,
        version=1,
    )
    reporte = ReporteRepository(session).crear(reporte)
    registrar_acceso(session, accion="reporte_creado", usuario_id=usuario.id, recurso=str(reporte.id), menor_id=reporte.menor_id)
    _programar_indexacion_reporte(tareas_fondo, session, reporte.id)
    return reporte


def _puede_ver_reporte(session, usuario, reporte: Reporte) -> bool:
    from app.modules.menores.application import puede_ver_menor, tiene_permiso_seccion

    seccion = seccion_de_tipo_reporte(reporte.tipo_reporte)
    if seccion is None:
        return puede_ver_menor(session, usuario, reporte.menor_id)
    return tiene_permiso_seccion(session, usuario, reporte.menor_id, seccion)


def listar_reportes(session: Session, usuario, menor_id: uuid.UUID | None = None, tipo_reporte: str | None = None) -> list[Reporte]:
    crudo = ReporteRepository(session).listar(menor_id=menor_id, tipo_reporte=tipo_reporte)
    resultado = [r for r in crudo if _puede_ver_reporte(session, usuario, r)]
    registrar_acceso(session, accion="reportes_listados", usuario_id=usuario.id)
    return resultado


def obtener_reporte(session: Session, usuario, reporte_id: uuid.UUID) -> Reporte:
    reporte = ReporteRepository(session).por_id(reporte_id)
    if reporte is None:
        raise no_encontrado("Reporte no encontrado")
    if not _puede_ver_reporte(session, usuario, reporte):
        registrar_acceso(
            session, accion="reporte_consulta_denegada", usuario_id=usuario.id, recurso=str(reporte.id), menor_id=reporte.menor_id
        )
        raise prohibido()
    registrar_acceso(
        session, accion="reporte_consultado", usuario_id=usuario.id, recurso=str(reporte.id), menor_id=reporte.menor_id
    )
    return reporte


# ---------------------------------------------------------------------------
# Agregador por sección (reemplaza el placeholder del frontend)
# ---------------------------------------------------------------------------

SECCIONES_VALIDAS = ("familia", "salud", "psicosocial")

CATEGORIAS_POR_SECCION = {
    "familia": ("familia_red_apoyo",),
    "salud": ("salud",),
    "psicosocial": ("psicosocial",),
}

TIPOS_REPORTE_POR_SECCION = {
    "familia": ("informe_trabajo_social",),
    "salud": ("informe_medico", "informe_nutricion"),
    "psicosocial": ("informe_psicosocial",),
}


def seccion_expediente(session: Session, usuario, menor_id: uuid.UUID, seccion: str) -> tuple[list[Documento], list[Reporte]]:
    if seccion not in SECCIONES_VALIDAS:
        raise ValueError("Sección inválida")
    from app.modules.menores.application import tiene_permiso_seccion

    if not tiene_permiso_seccion(session, usuario, menor_id, seccion):
        registrar_acceso(
            session, accion="seccion_expediente_denegada", usuario_id=usuario.id, menor_id=menor_id, recurso=seccion
        )
        raise prohibido()

    repo_doc = DocumentoRepository(session)
    documentos: list[Documento] = []
    for categoria in CATEGORIAS_POR_SECCION[seccion]:
        documentos.extend(repo_doc.listar(menor_id=menor_id, categoria=categoria))

    repo_rep = ReporteRepository(session)
    reportes: list[Reporte] = []
    for tipo in TIPOS_REPORTE_POR_SECCION[seccion]:
        reportes.extend(repo_rep.listar(menor_id=menor_id, tipo_reporte=tipo))

    registrar_acceso(
        session, accion="seccion_expediente_consultada", usuario_id=usuario.id, menor_id=menor_id, recurso=seccion
    )
    return documentos, reportes
