import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.models import Usuario

from .application import (
    cerrar_asignacion,
    crear_asignacion,
    historial_asignacion,
    listar_asignaciones_visibles,
    obtener_asignacion,
    vigente_de_menor_visible,
)
from .schemas import AsignacionCerrar, AsignacionCreate, AsignacionHistoryOut, AsignacionOut

router = APIRouter(prefix="/asignaciones", tags=["Asignaciones y Traslados"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "asignaciones", "estado": "activo"}


@router.post("", response_model=AsignacionOut, status_code=status.HTTP_201_CREATED, summary="Crear ingreso o traslado")
def crear_asignacion_endpoint(
    datos: AsignacionCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> AsignacionOut:
    try:
        return crear_asignacion(session, usuario, datos)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("", response_model=list[AsignacionOut], summary="Listar asignaciones")
def listar_asignaciones_endpoint(
    menor_id: uuid.UUID | None = None,
    hogar_id: uuid.UUID | None = None,
    zona_id: uuid.UUID | None = None,
    estado_actual: str | None = None,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> list[AsignacionOut]:
    return listar_asignaciones_visibles(
        session, usuario, menor_id=menor_id, hogar_id=hogar_id, zona_id=zona_id, estado=estado_actual
    )


@router.get("/menor/{menor_id}/vigente", response_model=AsignacionOut | None, summary="Asignación vigente de un menor")
def vigente_de_menor_endpoint(
    menor_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> AsignacionOut | None:
    return vigente_de_menor_visible(session, usuario, menor_id)


@router.get("/{asignacion_id}", response_model=AsignacionOut, summary="Obtener asignación")
def obtener_asignacion_endpoint(
    asignacion_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> AsignacionOut:
    return obtener_asignacion(session, usuario, asignacion_id)


@router.put("/{asignacion_id}/cerrar", response_model=AsignacionOut, summary="Cerrar asignación (egreso)")
def cerrar_asignacion_endpoint(
    asignacion_id: uuid.UUID,
    datos: AsignacionCerrar,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> AsignacionOut:
    try:
        return cerrar_asignacion(session, usuario, asignacion_id, datos)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/{asignacion_id}/historial", response_model=list[AsignacionHistoryOut], summary="Historial de la asignación")
def historial_asignacion_endpoint(
    asignacion_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[AsignacionHistoryOut]:
    return historial_asignacion(session, usuario, asignacion_id)
