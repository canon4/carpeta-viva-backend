import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.deps import usuario_actual
from app.modules.auth.models import Usuario

from .application import (
    listar_modelos_disponibles,
    actualizar_configuracion,
    obtener_configuracion,
    probar_configuracion,
    apoyo_redaccion,
    clasificar_contenido,
    consultar,
    estado,
    listar_consultas,
    obtener_consulta,
    reindexar_pendientes,
    resumen_documento,
    resumen_menor,
)
from .schemas import (
    IaModelosOut,
    IaConfiguracionOut,
    IaConfiguracionUpdate,
    IaPruebaOut,
    ConsultaCreate,
    ConsultaMetadatosOut,
    ConsultaOut,
    EstadoIaOut,
    RedaccionApoyoCreate,
    RedaccionApoyoOut,
    ReindexarPendientesOut,
    ResumenDocumentoOut,
    ResumenMenorOut,
)

router = APIRouter(prefix="/ia", tags=["Asistente de IA"])


@router.get("/_estado", summary="Estado del módulo (health check, no confundir con GET /ia/estado)")
def modulo_estado() -> dict[str, str]:
    return {"modulo": "ia", "estado": "activo"}


@router.get("/estado", response_model=EstadoIaOut, summary="Configuración activa del asistente (admin)")
def estado_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> EstadoIaOut:
    return EstadoIaOut(**estado(usuario, session))


@router.get(
    "/configuracion",
    response_model=IaConfiguracionOut,
    summary="Proveedor, modelo y estado de la clave de API (admin; la clave nunca se devuelve)",
)
def obtener_configuracion_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> IaConfiguracionOut:
    return IaConfiguracionOut(**obtener_configuracion(session, usuario))


@router.put(
    "/configuracion",
    response_model=IaConfiguracionOut,
    summary="Cambia proveedor, modelo o clave de API (admin; la clave se guarda cifrada)",
)
def actualizar_configuracion_endpoint(
    datos: IaConfiguracionUpdate,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> IaConfiguracionOut:
    try:
        return IaConfiguracionOut(**actualizar_configuracion(session, usuario, datos))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get(
    "/configuracion/modelos",
    response_model=IaModelosOut,
    summary="Modelos que la cuenta puede usar, consultados al proveedor (admin)",
)
def listar_modelos_endpoint(
    proveedor: str | None = None,
    session: Session = Depends(get_session),
    usuario: Usuario = Depends(usuario_actual),
) -> IaModelosOut:
    try:
        return IaModelosOut(**listar_modelos_disponibles(session, usuario, proveedor))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.post(
    "/configuracion/probar",
    response_model=IaPruebaOut,
    summary="Prueba la conexión con el proveedor configurado, sin datos de expedientes (admin)",
)
def probar_configuracion_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> IaPruebaOut:
    return IaPruebaOut(**probar_configuracion(session, usuario))


@router.post("/consultas", response_model=ConsultaOut, summary="Pregunta en lenguaje natural (RAG con citas)")
def crear_consulta_endpoint(
    datos: ConsultaCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ConsultaOut:
    consulta = consultar(session, usuario, datos)
    return ConsultaOut.model_validate(consulta, from_attributes=True)


@router.get("/consultas", summary="Historial de consultas (propio, o todas para admin/auditor)")
def listar_consultas_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> list[ConsultaOut] | list[ConsultaMetadatosOut]:
    return listar_consultas(session, usuario)


@router.get("/consultas/{consulta_id}", summary="Detalle de una consulta")
def obtener_consulta_endpoint(
    consulta_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ConsultaOut | ConsultaMetadatosOut:
    return obtener_consulta(session, usuario, consulta_id)


@router.get("/menores/{menor_id}/resumen", response_model=ResumenMenorOut, summary="Resumen de IA del expediente")
def resumen_menor_endpoint(
    menor_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ResumenMenorOut:
    return resumen_menor(session, usuario, menor_id)


@router.get(
    "/documentos/{documento_id}/resumen", response_model=ResumenDocumentoOut, summary="Resumen de IA de un documento o reporte"
)
def resumen_documento_endpoint(
    documento_id: uuid.UUID, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ResumenDocumentoOut:
    return resumen_documento(session, usuario, documento_id)


@router.post("/redaccion/apoyo", response_model=RedaccionApoyoOut, summary="Borrador de informe con apoyo de IA")
def apoyo_redaccion_endpoint(
    datos: RedaccionApoyoCreate, session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> RedaccionApoyoOut:
    return apoyo_redaccion(session, usuario, datos)


@router.post(
    "/mantenimiento/reindexar-pendientes",
    response_model=ReindexarPendientesOut,
    summary="Reintenta la indexación de documentos/reportes sin fragmentos (admin)",
)
def reindexar_pendientes_endpoint(
    session: Session = Depends(get_session), usuario: Usuario = Depends(usuario_actual)
) -> ReindexarPendientesOut:
    return ReindexarPendientesOut(**reindexar_pendientes(session, usuario))


@router.post(
    "/documentos/clasificar",
    summary="Sugerencia de categoría antes de crear el documento (no persiste nada)",
)
async def clasificar_documento_endpoint(
    archivo: UploadFile = File(...), usuario: Usuario = Depends(usuario_actual)
) -> dict:
    """No está en la lista literal de endpoints de ADR-0010 sección 1.9 (que describe
    `clasificar_y_extraer` como un caso de uso interno llamado por `documentos.application`
    después de guardar); se agrega este endpoint propio, de solo sugerencia, para poder
    mostrar `categoria_sugerida`/`confianza` ANTES de guardar (sección 1.2, "se devuelve
    categoria_sugerida y confianza en la respuesta de carga") sin modificar el contrato de
    `POST /documentos` de ADR-0008 sin coordinarlo primero con `backend`. Deviación documentada
    en el informe final de esta tarea.

    Hueco de disponibilidad corregido en la revisión de cierre de seguridad: a diferencia de
    `POST /documentos`/`POST /documentos/{id}/version` (que validan tamaño con
    `documentos.application._validar_tamanio` antes de procesar), este endpoint no tenía límite
    de tamaño: cualquier usuario autenticado podía mandar repetidamente una imagen enorme (o una
    "bomba de descompresión" para Pillow/Tesseract) y agotar CPU/memoria del backend sin pasar
    por ningún límite, ya que no persiste nada y por eso no pasaba por esa validación. Se aplica
    el mismo límite de tamaño configurado (`ARCHIVOS_TAMANIO_MAXIMO_BYTES`)."""
    from app.core.config import get_settings

    contenido = await archivo.read()
    maximo = get_settings().archivos_tamanio_maximo_bytes
    if len(contenido) == 0 or len(contenido) > maximo:
        from fastapi import HTTPException

        raise HTTPException(
            422, f"El archivo debe tener contenido y no superar {maximo // (1024 * 1024)} MB"
        )
    categoria, confianza = clasificar_contenido(contenido, archivo.content_type or "application/octet-stream")
    return {"categoria_sugerida": categoria, "confianza": confianza}
