import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.models import Usuario

from .application import (
    actualizar_cita,
    cambiar_estado_cita,
    crear_cita,
    listar_citas,
    listar_proximas,
    obtener_cita,
    puede_ver_notas,
)
from .models import Cita
from .schemas import CitaCreate, CitaEstadoUpdate, CitaOut, CitaUpdate

router = APIRouter(prefix="/citas", tags=["Citas y Recordatorios"])


def _a_salida(session: Session, usuario: Usuario, cita: Cita) -> CitaOut:
    """Construye la salida y aplica la corrección obligatoria de seguridad (ADR-0009, sección 2):
    `notas` se pone en `null` si el solicitante no tiene permiso de sección para el tipo de cita.
    Se filtra sobre el esquema de salida, nunca mutando la entidad ORM (evita escribir por error
    un valor equivocado en un `commit` posterior de la misma petición)."""
    salida = CitaOut.model_validate(cita)
    if not puede_ver_notas(session, usuario, cita):
        salida.notas = None
    return salida


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "citas", "estado": "activo"}


@router.post("", response_model=CitaOut, status_code=status.HTTP_201_CREATED, summary="Crear cita")
def crear_cita_endpoint(
    datos: CitaCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> CitaOut:
    return _a_salida(session, usuario, crear_cita(session, usuario, datos))


@router.get("/proximas", response_model=list[CitaOut], summary="Próximas citas pendientes")
def listar_proximas_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[CitaOut]:
    return [_a_salida(session, usuario, c) for c in listar_proximas(session, usuario)]


@router.get("", response_model=list[CitaOut], summary="Listar citas")
def listar_citas_endpoint(
    menor_id: uuid.UUID | None = None,
    tipo: str | None = None,
    estado: str | None = None,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> list[CitaOut]:
    citas = listar_citas(session, usuario, menor_id=menor_id, tipo=tipo, estado=estado)
    return [_a_salida(session, usuario, c) for c in citas]


@router.get("/{cita_id}", response_model=CitaOut, summary="Obtener cita")
def obtener_cita_endpoint(
    cita_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> CitaOut:
    return _a_salida(session, usuario, obtener_cita(session, usuario, cita_id))


@router.put("/{cita_id}", response_model=CitaOut, summary="Reprogramar cita")
def actualizar_cita_endpoint(
    cita_id: uuid.UUID,
    datos: CitaUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> CitaOut:
    return _a_salida(session, usuario, actualizar_cita(session, usuario, cita_id, datos))


@router.put("/{cita_id}/estado", response_model=CitaOut, summary="Cambiar estado de la cita")
def cambiar_estado_cita_endpoint(
    cita_id: uuid.UUID,
    datos: CitaEstadoUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> CitaOut:
    try:
        return _a_salida(session, usuario, cambiar_estado_cita(session, usuario, cita_id, datos.estado))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
