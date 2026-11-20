import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.models import Usuario

from .application import (
    actualizar_menor,
    crear_familiar,
    crear_menor,
    crear_permiso,
    historial_menor,
    listar_familiares,
    listar_menores,
    hogar_vigente,
    listar_permisos,
    obtener_menor,
    panel_profesional,
    panel_zona,
    revocar_permiso,
)
from .schemas import (
    FamiliarCreate,
    FamiliarOut,
    HogarPanelGroup,
    HogarVigenteOut,
    MenorCreate,
    MenorHistoryOut,
    MenorOut,
    MenorUpdate,
    PermisoCreate,
    PermisoOut,
    ZonaPanelGroup,
)

router = APIRouter(prefix="/menores", tags=["Menores y Expedientes"])


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "menores", "estado": "activo"}


@router.post("", response_model=MenorOut, status_code=status.HTTP_201_CREATED, summary="Crear expediente de menor")
def crear_menor_endpoint(
    datos: MenorCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> MenorOut:
    return crear_menor(session, usuario, datos)


@router.get("", response_model=list[MenorOut], summary="Listar expedientes de menores")
def listar_menores_endpoint(
    zona_id: uuid.UUID | None = None,
    hogar_id: uuid.UUID | None = None,
    estado_actual: str | None = None,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> list[MenorOut]:
    return listar_menores(session, usuario, zona_id=zona_id, hogar_id=hogar_id, estado=estado_actual)


@router.get("/panel/profesional", response_model=list[ZonaPanelGroup], summary="Panel del profesional autenticado")
def panel_profesional_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[ZonaPanelGroup]:
    return panel_profesional(session, usuario)


@router.get("/panel/zona", response_model=list[HogarPanelGroup], summary="Panel de la zona del coordinador")
def panel_zona_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[HogarPanelGroup]:
    return panel_zona(session, usuario)


@router.get("/{menor_id}", response_model=MenorOut, summary="Obtener expediente de menor")
def obtener_menor_endpoint(
    menor_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> MenorOut:
    return obtener_menor(session, usuario, menor_id)


@router.put("/{menor_id}", response_model=MenorOut, summary="Actualizar expediente de menor")
def actualizar_menor_endpoint(
    menor_id: uuid.UUID,
    datos: MenorUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> MenorOut:
    return actualizar_menor(session, usuario, menor_id, datos)


@router.get("/{menor_id}/historial", response_model=list[MenorHistoryOut], summary="Historial del expediente")
def historial_menor_endpoint(
    menor_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[MenorHistoryOut]:
    return historial_menor(session, usuario, menor_id)


@router.get("/{menor_id}/familiares", response_model=list[FamiliarOut], summary="Listar familiares del menor")
def listar_familiares_endpoint(
    menor_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[FamiliarOut]:
    return listar_familiares(session, usuario, menor_id)


@router.post(
    "/{menor_id}/familiares",
    response_model=FamiliarOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar familiar del menor",
)
def crear_familiar_endpoint(
    menor_id: uuid.UUID,
    datos: FamiliarCreate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> FamiliarOut:
    return crear_familiar(session, usuario, menor_id, datos)


@router.get(
    "/{menor_id}/hogar-vigente",
    response_model=HogarVigenteOut | None,
    summary="Hogar, zona y madre actuales del menor (null si no tiene asignación vigente)",
)
def hogar_vigente_endpoint(
    menor_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> HogarVigenteOut | None:
    return hogar_vigente(session, usuario, menor_id)


@router.get("/{menor_id}/permisos", response_model=list[PermisoOut], summary="Listar permisos de expediente")
def listar_permisos_endpoint(
    menor_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[PermisoOut]:
    return listar_permisos(session, usuario, menor_id)


@router.post(
    "/{menor_id}/permisos",
    response_model=PermisoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Otorgar permiso de expediente a la madre (solo defensor asignado)",
)
def crear_permiso_endpoint(
    menor_id: uuid.UUID,
    datos: PermisoCreate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> PermisoOut:
    try:
        return crear_permiso(session, usuario, menor_id, datos)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.delete(
    "/{menor_id}/permisos/{permiso_id}",
    response_model=PermisoOut,
    summary="Revocar permiso de expediente (solo defensor asignado)",
)
def revocar_permiso_endpoint(
    menor_id: uuid.UUID,
    permiso_id: uuid.UUID,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> PermisoOut:
    return revocar_permiso(session, usuario, menor_id, permiso_id)
