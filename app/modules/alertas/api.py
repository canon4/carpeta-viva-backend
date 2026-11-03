import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.domain import Rol
from app.modules.auth.models import Usuario

from .application import (
    cerrar_alerta,
    generar_automaticas,
    listar_alertas,
    marcar_visto,
    mis_pendientes,
    obtener_alerta,
    panel,
    reportar_evasion,
)
from .models import Alerta
from .schemas import AlertaOut, ContactosEmergenciaOut, EvasionCreate, EvasionReportadaOut

router = APIRouter(prefix="/alertas", tags=["Alertas y Evasiones"])


def _a_salida(usuario: Usuario, alerta: Alerta) -> AlertaOut:
    """Auditor ve solo metadatos (ADR-0009, sección 1 "Autorización": "tipo, menor, fecha,
    estado, destinatarios y si cada uno la vio"): nunca `descripcion` ni `detalle`, que son
    texto/JSON libres y pueden contener narrativa sensible del caso (p. ej. circunstancias de
    una evasión). El resto del público autorizado (destinatario, generador, coordinador, admin)
    ve la alerta completa, sin cambios."""
    salida = AlertaOut.model_validate(alerta)
    if usuario.rol == Rol.AUDITOR.value:
        salida.descripcion = "(oculto para auditor: solo metadatos)"
        salida.detalle = None
    return salida


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "alertas", "estado": "activo"}


@router.post("/evasion", response_model=EvasionReportadaOut, summary="Reportar evasión")
def reportar_evasion_endpoint(
    datos: EvasionCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> EvasionReportadaOut:
    alerta, contactos = reportar_evasion(session, usuario, datos)
    return EvasionReportadaOut(alerta=alerta, contactos_emergencia=contactos)


@router.get("/mis-pendientes", response_model=list[AlertaOut], summary="Mis alertas pendientes")
def mis_pendientes_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[AlertaOut]:
    return mis_pendientes(session, usuario)


@router.get("/panel", response_model=list[AlertaOut], summary="Panel de alertas activas")
def panel_endpoint(session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)) -> list[AlertaOut]:
    return panel(session, usuario)


@router.post("/generar-automaticas", response_model=list[AlertaOut], summary="Generar alertas automáticas (RF9)")
def generar_automaticas_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[AlertaOut]:
    return generar_automaticas(session, usuario)


@router.get("", response_model=list[AlertaOut], summary="Listar alertas")
def listar_alertas_endpoint(
    menor_id: uuid.UUID | None = None,
    tipo: str | None = None,
    estado: str | None = None,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> list[AlertaOut]:
    alertas = listar_alertas(session, usuario, menor_id=menor_id, tipo=tipo, estado=estado)
    return [_a_salida(usuario, a) for a in alertas]


@router.get("/{alerta_id}", response_model=AlertaOut, summary="Obtener alerta")
def obtener_alerta_endpoint(
    alerta_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> AlertaOut:
    return _a_salida(usuario, obtener_alerta(session, usuario, alerta_id))


@router.put("/{alerta_id}/visto", summary="Marcar como vista (destinatario)")
def marcar_visto_endpoint(
    alerta_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> dict[str, str]:
    marcar_visto(session, usuario, alerta_id)
    return {"estado": "vista"}


@router.put("/{alerta_id}/cerrar", response_model=AlertaOut, summary="Cerrar alerta")
def cerrar_alerta_endpoint(
    alerta_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> AlertaOut:
    return cerrar_alerta(session, usuario, alerta_id)
