import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.models import Usuario

from .application import (
    actualizar_conviviente,
    actualizar_item,
    actualizar_red_apoyo,
    confirmar_recepcion_item,
    crear_conviviente,
    crear_item,
    crear_red_apoyo,
    listar_convivientes,
    listar_fotos_item,
    listar_items,
    listar_red_apoyo,
    obtener_foto_item,
    ocultar_foto_item,
    subir_foto_item,
)
from .schemas import (
    ConvivienteCreate,
    ConvivienteOut,
    ConvivienteUpdate,
    InventarioItemCreate,
    InventarioItemFotoOut,
    InventarioItemOut,
    InventarioItemUpdate,
    InventarioRecepcionConfirmar,
    RedApoyoCreate,
    RedApoyoOut,
    RedApoyoUpdate,
)

router = APIRouter(prefix="/inventario", tags=["Inventario del Hogar"])

# Mismo filtro que `documentos.api` para `Content-Disposition` (caracteres de control/comillas
# nunca deben pasar sin filtrar desde un nombre de archivo provisto por el cliente).
_CONTROL_O_COMILLAS = re.compile(r'[\x00-\x1f\x7f"]')


def _cabeceras_vista_foto(nombre_original: str | None) -> dict[str, str]:
    nombre = _CONTROL_O_COMILLAS.sub("", nombre_original or "").strip() or "foto"
    return {
        "Content-Disposition": f'inline; filename="{nombre}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "inventario", "estado": "activo"}


# ---------------------------------------------------------------------------
# Items (camas, muebles, otro)
# ---------------------------------------------------------------------------

@router.post("/items", response_model=InventarioItemOut, status_code=status.HTTP_201_CREATED, summary="Crear ítem de inventario")
def crear_item_endpoint(
    datos: InventarioItemCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> InventarioItemOut:
    return crear_item(session, usuario, datos)


@router.get("/items", response_model=list[InventarioItemOut], summary="Listar ítems de inventario de un hogar")
def listar_items_endpoint(
    hogar_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[InventarioItemOut]:
    return listar_items(session, usuario, hogar_id)


@router.put("/items/{item_id}", response_model=InventarioItemOut, summary="Actualizar ítem de inventario")
def actualizar_item_endpoint(
    item_id: uuid.UUID,
    datos: InventarioItemUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> InventarioItemOut:
    try:
        return actualizar_item(session, usuario, item_id, datos)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.put("/items/{item_id}/recepcion", response_model=InventarioItemOut, summary="Confirmar recepción de un ítem")
def confirmar_recepcion_endpoint(
    item_id: uuid.UUID,
    datos: InventarioRecepcionConfirmar,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> InventarioItemOut:
    try:
        return confirmar_recepcion_item(session, usuario, item_id, datos.estado)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.post(
    "/items/{item_id}/fotos",
    response_model=InventarioItemFotoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Subir foto de evidencia de recepción",
)
async def subir_foto_endpoint(
    item_id: uuid.UUID,
    archivo: UploadFile = File(...),
    declaracion_sin_menores: bool = Form(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> InventarioItemFotoOut:
    contenido = await archivo.read()
    try:
        return subir_foto_item(
            session,
            usuario,
            item_id,
            contenido,
            archivo.content_type or "application/octet-stream",
            archivo.filename or "foto",
            declaracion_sin_menores,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/items/{item_id}/fotos", response_model=list[InventarioItemFotoOut], summary="Listar fotos de un ítem")
def listar_fotos_endpoint(
    item_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[InventarioItemFotoOut]:
    return listar_fotos_item(session, usuario, item_id)


@router.get("/items/{item_id}/fotos/{foto_id}", summary="Ver foto de evidencia")
def obtener_foto_endpoint(
    item_id: uuid.UUID,
    foto_id: uuid.UUID,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> Response:
    foto, contenido = obtener_foto_item(session, usuario, item_id, foto_id)
    return Response(
        content=contenido,
        media_type=foto.mime_type or "application/octet-stream",
        headers=_cabeceras_vista_foto(f"foto-{foto.id}"),
    )


@router.put(
    "/items/{item_id}/fotos/{foto_id}/ocultar",
    response_model=InventarioItemFotoOut,
    summary="Ocultar foto de evidencia (solo admin, remediación)",
)
def ocultar_foto_endpoint(
    item_id: uuid.UUID,
    foto_id: uuid.UUID,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> InventarioItemFotoOut:
    return ocultar_foto_item(session, usuario, item_id, foto_id)


# ---------------------------------------------------------------------------
# Convivientes
# ---------------------------------------------------------------------------

@router.post("/convivientes", response_model=ConvivienteOut, status_code=status.HTTP_201_CREATED, summary="Registrar conviviente")
def crear_conviviente_endpoint(
    datos: ConvivienteCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ConvivienteOut:
    return crear_conviviente(session, usuario, datos)


@router.get("/convivientes", response_model=list[ConvivienteOut], summary="Listar convivientes de un hogar")
def listar_convivientes_endpoint(
    hogar_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[ConvivienteOut]:
    return listar_convivientes(session, usuario, hogar_id)


@router.put("/convivientes/{conviviente_id}", response_model=ConvivienteOut, summary="Actualizar conviviente (incluye desactivar)")
def actualizar_conviviente_endpoint(
    conviviente_id: uuid.UUID,
    datos: ConvivienteUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> ConvivienteOut:
    return actualizar_conviviente(session, usuario, conviviente_id, datos)


# ---------------------------------------------------------------------------
# Red de apoyo
# ---------------------------------------------------------------------------

@router.post("/red-apoyo", response_model=RedApoyoOut, status_code=status.HTTP_201_CREATED, summary="Registrar contacto de red de apoyo")
def crear_red_apoyo_endpoint(
    datos: RedApoyoCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> RedApoyoOut:
    return crear_red_apoyo(session, usuario, datos)


@router.get("/red-apoyo", response_model=list[RedApoyoOut], summary="Listar red de apoyo de un hogar")
def listar_red_apoyo_endpoint(
    hogar_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[RedApoyoOut]:
    return listar_red_apoyo(session, usuario, hogar_id)


@router.put("/red-apoyo/{contacto_id}", response_model=RedApoyoOut, summary="Actualizar contacto de red de apoyo")
def actualizar_red_apoyo_endpoint(
    contacto_id: uuid.UUID,
    datos: RedApoyoUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> RedApoyoOut:
    return actualizar_red_apoyo(session, usuario, contacto_id, datos)
