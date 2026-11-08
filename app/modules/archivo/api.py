import re
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.models import Usuario

from .application import cerrar_expediente, listar_archivados, obtener_estado, obtener_paquete
from .schemas import CerrarExpedienteRequest, ExpedienteArchivoOut

router = APIRouter(prefix="/archivo", tags=["Archivo y Cierre"])

# Mismo criterio que `documentos.api._CONTROL_O_COMILLAS`: nunca interpolar sin filtrar un
# nombre de archivo hacia una cabecera HTTP de respuesta.
_CONTROL_O_COMILLAS = re.compile(r'[\x00-\x1f\x7f"]')


def _cabeceras_descarga(nombre_original: str) -> dict[str, str]:
    nombre = _CONTROL_O_COMILLAS.sub("", nombre_original).strip() or "paquete"
    return {
        "Content-Disposition": f'attachment; filename="{nombre}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "archivo", "estado": "activo"}


@router.get("", response_model=list[ExpedienteArchivoOut], summary="Listar expedientes archivados")
def listar_endpoint(
    zona_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> list[ExpedienteArchivoOut]:
    return listar_archivados(session, usuario, zona_id=zona_id, desde=desde, hasta=hasta)


@router.post(
    "/menores/{menor_id}/cerrar",
    response_model=ExpedienteArchivoOut,
    summary="Archivar y cerrar el expediente de un menor",
)
def cerrar_endpoint(
    menor_id: uuid.UUID,
    datos: CerrarExpedienteRequest,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> ExpedienteArchivoOut:
    try:
        return cerrar_expediente(session, usuario, menor_id, datos.motivo)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.get("/menores/{menor_id}", response_model=ExpedienteArchivoOut, summary="Estado de archivo de un menor")
def estado_endpoint(
    menor_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ExpedienteArchivoOut:
    return obtener_estado(session, usuario, menor_id)


@router.get("/menores/{menor_id}/paquete", summary="Descargar el paquete cifrado del expediente archivado")
def paquete_endpoint(
    menor_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> Response:
    _expediente, contenido = obtener_paquete(session, usuario, menor_id)
    return Response(
        content=contenido,
        media_type="application/zip",
        headers=_cabeceras_descarga(f"expediente_{menor_id}.zip"),
    )
