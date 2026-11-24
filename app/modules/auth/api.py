import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.core.tipos_archivo import detectar_tipo

from .application import (
    actualizar_mi_nombre,
    cambiar_contrasena,
    iniciar_sesion,
    obtener_foto_de_usuario,
    obtener_mi_foto,
    subir_mi_foto,
)
from .models import Usuario
from .schemas import CambioContrasenaRequest, LoginRequest, TokenOut, UsuarioAutoUpdate, UsuarioOut

router = APIRouter(prefix="/auth", tags=["Autenticación y Accesos"])
usuarios_router = APIRouter(prefix="/usuarios", tags=["Autenticación y Accesos"])


def _respuesta_foto(contenido: bytes, nombre: str) -> Response:
    tipo = detectar_tipo(contenido) or "application/octet-stream"
    return Response(
        content=contenido,
        media_type=tipo,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{nombre}"',
            # Defensa en profundidad: aunque el tipo ya se valida al subir (ADR-0019), se evita
            # que el navegador reinterprete el contenido si algo falla en esa validación (mismo
            # patrón que `inventario._cabeceras_vista_foto`, ADR-0014).
            "X-Content-Type-Options": "nosniff",
        },
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Iniciar sesión",
    responses={429: {"description": "Cuenta bloqueada temporalmente por intentos fallidos"}},
)
def login(datos: LoginRequest, request: Request, session: Session = Depends(get_session)) -> TokenOut:
    return TokenOut(access_token=iniciar_sesion(session, datos.email, datos.password, _ip(request)))


@router.get("/me", response_model=UsuarioOut, summary="Usuario autenticado")
def me(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    return usuario


@router.put(
    "/contrasena",
    response_model=TokenOut,
    summary="Cambiar la contraseña propia (invalida las sesiones anteriores y devuelve un token nuevo)",
)
def cambiar_contrasena_endpoint(
    datos: CambioContrasenaRequest,
    request: Request,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> TokenOut:
    try:
        token = cambiar_contrasena(session, usuario, datos.actual, datos.nueva, _ip(request))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return TokenOut(access_token=token)


@router.put("/yo", response_model=UsuarioOut, summary="Actualizar nombre propio (solo coordinador, admin, auditor)")
def actualizar_mi_nombre_endpoint(
    datos: UsuarioAutoUpdate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> Usuario:
    return actualizar_mi_nombre(session, usuario, datos.nombres, datos.apellidos)


@router.put("/yo/foto", response_model=UsuarioOut, summary="Subir o reemplazar la foto de perfil propia")
async def subir_mi_foto_endpoint(
    archivo: UploadFile = File(...),
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> Usuario:
    contenido = await archivo.read()
    try:
        return subir_mi_foto(session, usuario, contenido)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/yo/foto", summary="Ver la foto de perfil propia")
def obtener_mi_foto_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> Response:
    return _respuesta_foto(obtener_mi_foto(session, usuario), f"foto-{usuario.id}")


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "auth", "estado": "activo"}


@usuarios_router.get("/{usuario_id}/foto", summary="Ver la foto de perfil de cualquier usuario")
def obtener_foto_de_usuario_endpoint(
    usuario_id: uuid.UUID,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> Response:
    return _respuesta_foto(obtener_foto_de_usuario(session, usuario, usuario_id), f"foto-{usuario_id}")


# `usuarios_router` no va bajo el prefijo `/auth` (es `/usuarios/{id}/foto`, directorio de
# personal, no autenticación): `registry.routers()` lo recoge aparte vía `routers_extra`.
routers_extra = [usuarios_router]
