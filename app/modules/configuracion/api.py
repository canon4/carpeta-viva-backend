from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import requiere_roles, usuario_actual
from app.modules.auth.domain import Rol
from app.modules.auth.models import Usuario

from .application import (
    actualizar_opcion_catalogo,
    actualizar_parametro,
    crear_opcion_catalogo,
    listar_catalogo_admin,
    listar_catalogo_publico,
    listar_grupos_catalogo,
    listar_parametros,
    listar_parametros_publicos,
    obtener_parametro_admin,
)
from .schemas import (
    CatalogoOpcionAdminOut,
    CatalogoOpcionCreate,
    CatalogoOpcionOut,
    CatalogoOpcionUpdate,
    GrupoCatalogoOut,
    ParametroOut,
    ParametroPublicoOut,
    ParametroUpdate,
)

router = APIRouter(prefix="/configuracion", tags=["Configuración administrable"])

_admin = requiere_roles(Rol.ADMIN)


@router.get("/_estado", summary="Estado del módulo")
def estado() -> dict[str, str]:
    return {"modulo": "configuracion", "estado": "activo"}


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------

@router.get("/catalogos", response_model=list[GrupoCatalogoOut], summary="Listar grupos de catálogo (admin)")
def listar_grupos_catalogo_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(_admin)
) -> list[GrupoCatalogoOut]:
    return listar_grupos_catalogo(session, usuario)


@router.get(
    "/catalogos/{grupo}",
    response_model=list[CatalogoOpcionOut],
    summary="Listar opciones activas de un catálogo (cualquier autenticado)",
)
def listar_catalogo_publico_endpoint(
    grupo: str, session: Session = Depends(get_session), _usuario: Usuario = Depends(usuario_actual)
) -> list[CatalogoOpcionOut]:
    return listar_catalogo_publico(session, grupo)


@router.get(
    "/catalogos/{grupo}/admin",
    response_model=list[CatalogoOpcionAdminOut],
    summary="Listar opciones de un catálogo, incluidas inactivas (admin)",
)
def listar_catalogo_admin_endpoint(
    grupo: str, session: Session = Depends(get_session), usuario: Usuario = Depends(_admin)
) -> list[CatalogoOpcionAdminOut]:
    return listar_catalogo_admin(session, usuario, grupo)


@router.post(
    "/catalogos/{grupo}",
    response_model=CatalogoOpcionAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear opción de catálogo (admin)",
)
def crear_opcion_catalogo_endpoint(
    grupo: str,
    datos: CatalogoOpcionCreate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(_admin),
) -> CatalogoOpcionAdminOut:
    try:
        return crear_opcion_catalogo(
            session,
            usuario,
            grupo,
            datos.valor,
            datos.etiqueta,
            orden=datos.orden,
            seccion_acceso=datos.seccion_acceso,
            seccion_acceso_fue_enviada="seccion_acceso" in datos.model_fields_set,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.put(
    "/catalogos/{grupo}/{valor}",
    response_model=CatalogoOpcionAdminOut,
    summary="Editar o desactivar opción de catálogo (admin)",
)
def actualizar_opcion_catalogo_endpoint(
    grupo: str,
    valor: str,
    datos: CatalogoOpcionUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(_admin),
) -> CatalogoOpcionAdminOut:
    return actualizar_opcion_catalogo(
        session, usuario, grupo, valor, etiqueta=datos.etiqueta, orden=datos.orden, activo=datos.activo
    )


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

@router.get("/parametros", response_model=list[ParametroOut], summary="Listar parámetros (admin)")
def listar_parametros_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(_admin)
) -> list[ParametroOut]:
    return listar_parametros(session, usuario)


@router.get("/parametros/{clave}", response_model=ParametroOut, summary="Detalle de un parámetro (admin)")
def obtener_parametro_endpoint(
    clave: str, session: Session = Depends(get_session), usuario: Usuario = Depends(_admin)
) -> ParametroOut:
    return obtener_parametro_admin(session, usuario, clave)


@router.put("/parametros/{clave}", response_model=ParametroOut, summary="Actualizar un parámetro (admin)")
def actualizar_parametro_endpoint(
    clave: str,
    datos: ParametroUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(_admin),
) -> ParametroOut:
    try:
        return actualizar_parametro(session, usuario, clave, datos.valor)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get(
    "/publica",
    response_model=list[ParametroPublicoOut],
    summary="Parámetros públicos (cualquier autenticado)",
)
def listar_parametros_publicos_endpoint(
    session: Session = Depends(get_session), _usuario: Usuario = Depends(usuario_actual)
) -> list[ParametroPublicoOut]:
    return listar_parametros_publicos(session)
