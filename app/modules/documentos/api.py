import re
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.models import Usuario

from .application import (
    aprobar_documento,
    crear_documento,
    crear_reporte,
    crear_version,
    descargar_documento,
    descargar_version,
    devolver_documento,
    enviar_documento,
    listar_documentos,
    listar_para_auditor,
    listar_reportes,
    listar_versiones,
    obtener_documento,
    obtener_reporte,
    seccion_expediente,
)
from .schemas import (
    DocumentoDevolver,
    DocumentoOut,
    DocumentoVersionOut,
    ReporteCreate,
    ReporteOut,
    SeccionExpedienteOut,
)

router = APIRouter(prefix="/documentos", tags=["Gestión Documental"])

# Caracteres de control (incluye CR/LF, que podrían inyectar una cabecera HTTP adicional) y
# comillas (que romperían el valor de `filename="..."`) nunca deben pasar sin filtrar desde un
# nombre de archivo provisto por el cliente hacia una cabecera de respuesta.
_CONTROL_O_COMILLAS = re.compile(r'[\x00-\x1f\x7f"]')


def _cabeceras_descarga(nombre_original: str | None) -> dict[str, str]:
    """Cabeceras para servir contenido descifrado: `Content-Disposition` con el nombre saneado
    (nunca se interpola el valor del cliente sin filtrar), `nosniff` (el `mime_type` viene del
    cliente y no es confiable) y `no-store` (nunca cachear contenido de expedientes de NNA)."""
    nombre = _CONTROL_O_COMILLAS.sub("", nombre_original or "").strip() or "documento"
    return {
        "Content-Disposition": f'attachment; filename="{nombre}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "documentos", "estado": "activo"}


@router.post("", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED, summary="Crear documento")
async def crear_documento_endpoint(
    tareas_fondo: BackgroundTasks,
    archivo: UploadFile = File(...),
    categoria: str = Form(...),
    titulo: str = Form(...),
    menor_id: uuid.UUID | None = Form(None),
    hogar_id: uuid.UUID | None = Form(None),
    migracion: bool = Form(False),
    motivo: str | None = Form(None),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> DocumentoOut:
    contenido = await archivo.read()
    try:
        return crear_documento(
            session,
            usuario,
            menor_id=menor_id,
            hogar_id=hogar_id,
            categoria=categoria,
            titulo=titulo,
            contenido=contenido,
            nombre_original=archivo.filename or "sin_nombre",
            mime_type=archivo.content_type or "application/octet-stream",
            migracion=migracion,
            motivo=motivo,
            tareas_fondo=tareas_fondo,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/auditor", response_model=list[DocumentoOut], summary="Metadatos para auditor (sin contenido)")
def listar_para_auditor_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[DocumentoOut]:
    return listar_para_auditor(session, usuario)


@router.get("", response_model=list[DocumentoOut], summary="Listar documentos")
def listar_documentos_endpoint(
    menor_id: uuid.UUID | None = None,
    hogar_id: uuid.UUID | None = None,
    categoria: str | None = None,
    estado_flujo: str | None = None,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> list[DocumentoOut]:
    return listar_documentos(
        session, usuario, menor_id=menor_id, hogar_id=hogar_id, categoria=categoria, estado_flujo=estado_flujo
    )


@router.get("/menor/{menor_id}/seccion/{seccion}", response_model=SeccionExpedienteOut, summary="Documentos y reportes de una sección")
def seccion_expediente_endpoint(
    menor_id: uuid.UUID,
    seccion: str,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> SeccionExpedienteOut:
    try:
        documentos, reportes = seccion_expediente(session, usuario, menor_id, seccion)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return SeccionExpedienteOut(menor_id=menor_id, seccion=seccion, documentos=documentos, reportes=reportes)


@router.post("/reportes", response_model=ReporteOut, status_code=status.HTTP_201_CREATED, summary="Crear reporte")
def crear_reporte_endpoint(
    datos: ReporteCreate,
    tareas_fondo: BackgroundTasks,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> ReporteOut:
    return crear_reporte(session, usuario, datos, tareas_fondo=tareas_fondo)


@router.get("/reportes", response_model=list[ReporteOut], summary="Listar reportes")
def listar_reportes_endpoint(
    menor_id: uuid.UUID | None = None,
    tipo_reporte: str | None = None,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> list[ReporteOut]:
    return listar_reportes(session, usuario, menor_id=menor_id, tipo_reporte=tipo_reporte)


@router.get("/reportes/{reporte_id}", response_model=ReporteOut, summary="Obtener reporte")
def obtener_reporte_endpoint(
    reporte_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ReporteOut:
    return obtener_reporte(session, usuario, reporte_id)


@router.get("/{documento_id}", response_model=DocumentoOut, summary="Obtener documento (metadatos)")
def obtener_documento_endpoint(
    documento_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> DocumentoOut:
    return obtener_documento(session, usuario, documento_id)


@router.get("/{documento_id}/contenido", summary="Descargar contenido descifrado")
def descargar_documento_endpoint(
    documento_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> Response:
    documento, contenido = descargar_documento(session, usuario, documento_id)
    return Response(
        content=contenido,
        media_type=documento.mime_type or "application/octet-stream",
        headers=_cabeceras_descarga(documento.nombre_original),
    )


@router.put("/{documento_id}/enviar", response_model=DocumentoOut, summary="Enviar a revisión")
def enviar_documento_endpoint(
    documento_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> DocumentoOut:
    try:
        return enviar_documento(session, usuario, documento_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.put("/{documento_id}/aprobar", response_model=DocumentoOut, summary="Aprobar documento")
def aprobar_documento_endpoint(
    documento_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> DocumentoOut:
    try:
        return aprobar_documento(session, usuario, documento_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.put("/{documento_id}/devolver", response_model=DocumentoOut, summary="Devolver documento")
def devolver_documento_endpoint(
    documento_id: uuid.UUID,
    datos: DocumentoDevolver,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> DocumentoOut:
    try:
        return devolver_documento(session, usuario, documento_id, datos.motivo)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.post("/{documento_id}/version", response_model=DocumentoOut, summary="Subir nueva versión")
async def crear_version_endpoint(
    documento_id: uuid.UUID,
    tareas_fondo: BackgroundTasks,
    archivo: UploadFile = File(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> DocumentoOut:
    contenido = await archivo.read()
    try:
        return crear_version(
            session,
            usuario,
            documento_id,
            contenido=contenido,
            nombre_original=archivo.filename or "sin_nombre",
            mime_type=archivo.content_type or "application/octet-stream",
            tareas_fondo=tareas_fondo,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/{documento_id}/versiones", response_model=list[DocumentoVersionOut], summary="Listar versiones anteriores")
def listar_versiones_endpoint(
    documento_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[DocumentoVersionOut]:
    return listar_versiones(session, usuario, documento_id)


@router.get("/{documento_id}/versiones/{version}/contenido", summary="Descargar una versión anterior")
def descargar_version_endpoint(
    documento_id: uuid.UUID,
    version: int,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> Response:
    version_obj, contenido = descargar_version(session, usuario, documento_id, version)
    return Response(
        content=contenido,
        media_type=version_obj.mime_type or "application/octet-stream",
        headers=_cabeceras_descarga(version_obj.nombre_original),
    )
