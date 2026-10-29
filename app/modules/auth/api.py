from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual

from .application import iniciar_sesion
from .models import Usuario
from .schemas import LoginRequest, TokenOut, UsuarioOut

router = APIRouter(prefix="/auth", tags=["Autenticación y Accesos"])


@router.post("/login", response_model=TokenOut, summary="Iniciar sesión")
def login(datos: LoginRequest, request: Request, session: Session = Depends(get_session)) -> TokenOut:
    ip = request.client.host if request.client else None
    return TokenOut(access_token=iniciar_sesion(session, datos.email, datos.password, ip))


@router.get("/me", response_model=UsuarioOut, summary="Usuario autenticado")
def me(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    return usuario


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "auth", "estado": "activo"}
