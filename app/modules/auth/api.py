from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual

from .application import cambiar_contrasena, iniciar_sesion
from .models import Usuario
from .schemas import CambioContrasenaRequest, LoginRequest, TokenOut, UsuarioOut

router = APIRouter(prefix="/auth", tags=["Autenticación y Accesos"])


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


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "auth", "estado": "activo"}
