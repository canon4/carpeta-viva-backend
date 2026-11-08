import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.models import Usuario

from .application import (
    exportar_informe,
    listar_exportados,
    obtener_contenido_exportado,
    reporte_general,
    reporte_madre,
    reporte_menor,
    reporte_zona,
)
from .schemas import ExportarRequest, InformeGeneradoOut, ReporteAgregadoOut, ReporteMadreOut, ReporteMenorOut

router = APIRouter(prefix="/reportes", tags=["Reportes"])

_CONTROL_O_COMILLAS = re.compile(r'[\x00-\x1f\x7f"]')

_MIME_POR_FORMATO = {
    "json": "application/json",
    "csv": "text/csv",
    "pdf": "application/pdf",
}


def _cabeceras_descarga(nombre_original: str) -> dict[str, str]:
    nombre = _CONTROL_O_COMILLAS.sub("", nombre_original).strip() or "informe"
    return {
        "Content-Disposition": f'attachment; filename="{nombre}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "reportes", "estado": "activo"}


@router.get("/general", response_model=ReporteAgregadoOut, summary="Reporte general")
def general_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ReporteAgregadoOut:
    return reporte_general(session, usuario)


@router.get("/zona/{zona_id}", response_model=ReporteAgregadoOut, summary="Reporte por zona")
def zona_endpoint(
    zona_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ReporteAgregadoOut:
    return reporte_zona(session, usuario, zona_id)


@router.get("/menor/{menor_id}", response_model=ReporteMenorOut, summary="Reporte por menor")
def menor_endpoint(
    menor_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ReporteMenorOut:
    return reporte_menor(session, usuario, menor_id)


@router.get("/madre/{madre_id}", response_model=ReporteMadreOut, summary="Reporte por madre")
def madre_endpoint(
    madre_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ReporteMadreOut:
    return reporte_madre(session, usuario, madre_id)


@router.post(
    "/exportar", response_model=InformeGeneradoOut, status_code=status.HTTP_201_CREATED, summary="Exportar reporte"
)
def exportar_endpoint(
    datos: ExportarRequest, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> InformeGeneradoOut:
    try:
        return exportar_informe(session, usuario, datos)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/exportados", response_model=list[InformeGeneradoOut], summary="Listar informes exportados")
def listar_exportados_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[InformeGeneradoOut]:
    return listar_exportados(session, usuario)


@router.get("/exportados/{informe_id}/contenido", summary="Descargar un informe exportado")
def contenido_exportado_endpoint(
    informe_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> Response:
    informe, contenido = obtener_contenido_exportado(session, usuario, informe_id)
    mime = _MIME_POR_FORMATO.get(informe.formato, "application/octet-stream")
    return Response(
        content=contenido,
        media_type=mime,
        headers=_cabeceras_descarga(f"informe_{informe.nivel}_{informe_id}.{informe.formato}"),
    )
