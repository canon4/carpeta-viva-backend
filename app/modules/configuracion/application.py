"""Configuración administrable: casos de uso (ADR-0013).

Transversal: no modela una entidad de negocio propia, solo sirve catálogos y parámetros a los
demás módulos (`documentos`, `alertas`, ...) a través de esta capa de aplicación — nunca tocan
`catalogos_opciones`/`configuracion_sistema` directamente (sección 0 del ADR).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido
from app.modules.auth.domain import Rol

from .domain import GRUPOS_CATALOGO, REGISTRO_PARAMETROS, SECCIONES_VALIDAS
from .models import CatalogoOpcion, ConfiguracionParametro
from .repository import CatalogoOpcionRepository, ConfiguracionParametroRepository
from .schemas import (
    CatalogoOpcionAdminOut,
    CatalogoOpcionOut,
    GrupoCatalogoOut,
    ParametroOut,
)

# ---------------------------------------------------------------------------
# Semilla de respaldo (ADR-0013, sección 7.1): la migración 0009 siembra estas mismas opciones
# en Postgres. Este diccionario solo existe para que un entorno que arma el esquema con
# `Base.metadata.create_all` y nunca corre migraciones (pruebas, mismo caso ya documentado en
# `alertas/repository.ConfiguracionAlertasRepository`) no se quede sin categorías documentales
# básicas. Si `catalogos_opciones` ya tiene alguna fila para el grupo, nunca se vuelve a sembrar.
# ---------------------------------------------------------------------------
_SEED_CATALOGOS: dict[str, list[tuple[str, str, int, str | None]]] = {
    "categoria_documento_menor": [
        ("identidad", "Identidad", 0, None),
        ("salud", "Salud", 1, "salud"),
        ("psicosocial", "Psicosocial", 2, "psicosocial"),
        ("educacion", "Educación", 3, None),
        ("familia_red_apoyo", "Familia y red de apoyo", 4, "familia"),
        ("actas_traslados", "Actas de traslado", 5, None),
        ("otros", "Otros", 6, None),
    ],
    "categoria_documento_hogar": [
        ("madre_habilitacion", "Habilitación de la madre", 0, None),
        ("otros", "Otros", 1, None),
    ],
}


def _asegurar_semilla(session: Session, grupo: str) -> None:
    if grupo not in _SEED_CATALOGOS:
        return
    repo = CatalogoOpcionRepository(session)
    if repo.contar_todas(grupo) > 0:
        return
    for valor, etiqueta, orden, seccion_acceso in _SEED_CATALOGOS[grupo]:
        repo.crear(
            CatalogoOpcion(grupo=grupo, valor=valor, etiqueta=etiqueta, orden=orden, seccion_acceso=seccion_acceso)
        )


# ---------------------------------------------------------------------------
# Catálogos — lectura (usada por otros módulos y por la pantalla de administración)
# ---------------------------------------------------------------------------

def obtener_opciones_catalogo(session: Session, grupo: str, solo_activas: bool = True) -> list[CatalogoOpcion]:
    """Usada por otros módulos (p.ej. `documentos`) y por `GET /configuracion/catalogos/{grupo}`."""
    _asegurar_semilla(session, grupo)
    return CatalogoOpcionRepository(session).listar(grupo, solo_activas=solo_activas)


def valor_valido_en_catalogo(session: Session, grupo: str, valor: str) -> bool:
    """`True` si `valor` está activo dentro de `grupo`. Usada por `documentos.application` para
    validar la categoría recibida al crear/actualizar un documento (ADR-0013, consecuencias)."""
    opciones = obtener_opciones_catalogo(session, grupo, solo_activas=True)
    return any(o.valor == valor for o in opciones)


def seccion_acceso_de_opcion(session: Session, grupo: str, valor: str) -> str | None:
    """Backstop defensivo (ADR-0013, sección 5.1): nunca levanta una sección sensible por
    defecto. Devuelve `None` si la opción no existe, está inactiva, o si el valor guardado en
    BD no es uno de `SECCIONES_VALIDAS` (fila corrupta / migración manual)."""
    opcion = CatalogoOpcionRepository(session).por_grupo_y_valor(grupo, valor)
    if opcion is None or not opcion.activo:
        return None
    if opcion.seccion_acceso not in SECCIONES_VALIDAS:
        return None
    return opcion.seccion_acceso


def listar_grupos_catalogo(session: Session, usuario) -> list[GrupoCatalogoOut]:
    _requiere_admin(usuario, session, "catalogos_grupos_consulta_denegada")
    resultado = []
    for grupo, definicion in GRUPOS_CATALOGO.items():
        activas = obtener_opciones_catalogo(session, grupo, solo_activas=True)
        resultado.append(
            GrupoCatalogoOut(
                grupo=grupo,
                etiqueta=definicion.etiqueta,
                descripcion=definicion.descripcion,
                con_seccion_acceso=definicion.con_seccion_acceso,
                total_opciones_activas=len(activas),
            )
        )
    registrar_acceso(session, accion="catalogos_grupos_listados", usuario_id=usuario.id)
    return resultado


def listar_catalogo_publico(session: Session, grupo: str) -> list[CatalogoOpcionOut]:
    """`GET /configuracion/catalogos/{grupo}`: cualquier autenticado (ADR-0013, sección 3/5.1 —
    las etiquetas de categorías documentales no son dato personal ni información sensible)."""
    _grupo_o_404(grupo)
    opciones = obtener_opciones_catalogo(session, grupo, solo_activas=True)
    return [CatalogoOpcionOut.model_validate(o) for o in opciones]


def listar_catalogo_admin(session: Session, usuario, grupo: str) -> list[CatalogoOpcionAdminOut]:
    _requiere_admin(usuario, session, "catalogo_admin_consulta_denegada")
    _grupo_o_404(grupo)
    opciones = obtener_opciones_catalogo(session, grupo, solo_activas=False)
    registrar_acceso(session, accion="catalogo_admin_consultado", usuario_id=usuario.id, recurso=grupo)
    return [CatalogoOpcionAdminOut.model_validate(o) for o in opciones]


# ---------------------------------------------------------------------------
# Catálogos — escritura (admin)
# ---------------------------------------------------------------------------

def _grupo_o_404(grupo: str) -> None:
    if grupo not in GRUPOS_CATALOGO:
        raise no_encontrado(f"Grupo de catálogo desconocido: {grupo}")


def _requiere_admin(usuario, session: Session, accion_denegada: str) -> None:
    if usuario.rol != Rol.ADMIN.value:
        registrar_acceso(session, accion=accion_denegada, usuario_id=usuario.id)
        raise prohibido()


def crear_opcion_catalogo(
    session: Session,
    usuario,
    grupo: str,
    valor: str,
    etiqueta: str,
    orden: int = 0,
    seccion_acceso: str | None = None,
) -> CatalogoOpcion:
    """`POST /configuracion/catalogos/{grupo}` (ADR-0013, sección 3 y 5.1). Si el grupo exige
    `seccion_acceso`, es obligatorio (puede ser explícitamente básica = `None`) y debe estar en
    `SECCIONES_VALIDAS`; rechaza con 400 en cualquier otro caso."""
    _requiere_admin(usuario, session, "catalogo_opcion_creacion_denegada")
    if grupo not in GRUPOS_CATALOGO:
        raise ValueError(f"Grupo de catálogo desconocido: {grupo}")
    definicion = GRUPOS_CATALOGO[grupo]

    if definicion.con_seccion_acceso:
        if seccion_acceso is not None and seccion_acceso not in SECCIONES_VALIDAS:
            raise ValueError(
                f"seccion_acceso debe ser uno de {SECCIONES_VALIDAS} o None (básica), recibido: {seccion_acceso!r}"
            )
    else:
        seccion_acceso = None

    _asegurar_semilla(session, grupo)
    repo = CatalogoOpcionRepository(session)
    if repo.por_grupo_y_valor(grupo, valor) is not None:
        raise ValueError(f"Ya existe la opción '{valor}' en el grupo '{grupo}'")

    opcion = CatalogoOpcion(
        grupo=grupo,
        valor=valor,
        etiqueta=etiqueta,
        orden=orden,
        activo=True,
        seccion_acceso=seccion_acceso,
        actualizado_por=usuario.id,
    )
    opcion = repo.crear(opcion)

    # Auditoría distinta para grupos con lógica de permisos asociada (ADR-0013, sección 5.1):
    # deja constancia explícita de qué sección eligió el admin en el mismo evento de creación.
    if definicion.con_seccion_acceso:
        registrar_acceso(
            session,
            accion="catalogo_categoria_documental_creada",
            usuario_id=usuario.id,
            recurso=f"{grupo}:{valor}",
        )
    else:
        registrar_acceso(
            session, accion="catalogo_opcion_creada", usuario_id=usuario.id, recurso=f"{grupo}:{valor}"
        )
    return opcion


def actualizar_opcion_catalogo(
    session: Session,
    usuario,
    grupo: str,
    valor: str,
    etiqueta: str | None = None,
    orden: int | None = None,
    activo: bool | None = None,
) -> CatalogoOpcion:
    """`PUT /configuracion/catalogos/{grupo}/{valor}`: solo etiqueta/orden/activo. `seccion_acceso`
    es inmutable tras la creación (ADR-0013, sección 5.1) — no se acepta aquí."""
    _requiere_admin(usuario, session, "catalogo_opcion_edicion_denegada")
    _grupo_o_404(grupo)
    repo = CatalogoOpcionRepository(session)
    opcion = repo.por_grupo_y_valor(grupo, valor)
    if opcion is None:
        raise no_encontrado(f"No existe la opción '{valor}' en el grupo '{grupo}'")

    if etiqueta is not None:
        opcion.etiqueta = etiqueta
    if orden is not None:
        opcion.orden = orden
    if activo is not None:
        opcion.activo = activo
    opcion.actualizado_en = datetime.now(timezone.utc)
    opcion.actualizado_por = usuario.id
    opcion = repo.guardar(opcion)
    registrar_acceso(session, accion="catalogo_opcion_actualizada", usuario_id=usuario.id, recurso=f"{grupo}:{valor}")
    return opcion


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

def _castear(tipo: str, valor: str) -> None:
    """Valida (sin transformar lo guardado, que siempre queda como texto) que `valor` respete el
    tipo declarado en el registro antes de aceptarlo."""
    if tipo == "int":
        int(valor)
    elif tipo == "bool":
        if valor.strip().lower() not in ("true", "false", "1", "0"):
            raise ValueError("Valor booleano inválido: use 'true' o 'false'")
    # "str": cualquier texto es válido.


def obtener_parametro(session: Session, clave: str) -> str:
    """Usada por otros módulos (p.ej. `alertas`). Devuelve el valor guardado, o
    `valor_por_defecto` del registro si la fila no existe o está vacía (ADR-0013, sección 7.4)."""
    if clave not in REGISTRO_PARAMETROS:
        raise ValueError(f"Parámetro desconocido: {clave}")
    parametro = ConfiguracionParametroRepository(session).por_clave(clave)
    if parametro is not None and parametro.valor:
        return parametro.valor
    return REGISTRO_PARAMETROS[clave].valor_por_defecto


def listar_parametros(session: Session, usuario) -> list[ParametroOut]:
    _requiere_admin(usuario, session, "parametros_consulta_denegada")
    repo = ConfiguracionParametroRepository(session)
    resultado = []
    for clave, definicion in REGISTRO_PARAMETROS.items():
        guardado = repo.por_clave(clave)
        editado = guardado is not None and bool(guardado.valor)
        resultado.append(
            ParametroOut(
                clave=clave,
                etiqueta=clave.replace("_", " ").capitalize(),
                descripcion=definicion.descripcion,
                tipo=definicion.tipo,
                grupo=definicion.grupo,
                publico=definicion.publico,
                valor_actual=guardado.valor if (guardado and guardado.valor) else definicion.valor_por_defecto,
                valor_por_defecto=definicion.valor_por_defecto,
                editado_por_admin=editado,
            )
        )
    registrar_acceso(session, accion="parametros_listados", usuario_id=usuario.id)
    return resultado


def obtener_parametro_admin(session: Session, usuario, clave: str) -> ParametroOut:
    _requiere_admin(usuario, session, "parametro_consulta_denegada")
    if clave not in REGISTRO_PARAMETROS:
        raise no_encontrado(f"Parámetro desconocido: {clave}")
    definicion = REGISTRO_PARAMETROS[clave]
    guardado = ConfiguracionParametroRepository(session).por_clave(clave)
    editado = guardado is not None and bool(guardado.valor)
    registrar_acceso(session, accion="parametro_consultado", usuario_id=usuario.id, recurso=clave)
    return ParametroOut(
        clave=clave,
        etiqueta=clave.replace("_", " ").capitalize(),
        descripcion=definicion.descripcion,
        tipo=definicion.tipo,
        grupo=definicion.grupo,
        publico=definicion.publico,
        valor_actual=guardado.valor if (guardado and guardado.valor) else definicion.valor_por_defecto,
        valor_por_defecto=definicion.valor_por_defecto,
        editado_por_admin=editado,
    )


def actualizar_parametro(session: Session, usuario, clave: str, valor: str) -> ParametroOut:
    """`PUT /configuracion/parametros/{clave}`: upsert en `configuracion_sistema`, valida el
    tipo declarado en el registro antes de guardar."""
    _requiere_admin(usuario, session, "parametro_edicion_denegada")
    if clave not in REGISTRO_PARAMETROS:
        raise ValueError(f"Parámetro desconocido: {clave}")
    _castear(REGISTRO_PARAMETROS[clave].tipo, valor)

    repo = ConfiguracionParametroRepository(session)
    parametro = repo.por_clave(clave)
    ahora = datetime.now(timezone.utc)
    if parametro is None:
        parametro = ConfiguracionParametro(
            clave=clave, valor=valor, actualizado_en=ahora, actualizado_por=usuario.id
        )
        repo.crear(parametro)
    else:
        parametro.valor = valor
        parametro.actualizado_en = ahora
        parametro.actualizado_por = usuario.id
        repo.guardar(parametro)

    registrar_acceso(session, accion="parametro_actualizado", usuario_id=usuario.id, recurso=clave)
    return obtener_parametro_admin(session, usuario, clave)


def listar_parametros_publicos(session: Session) -> list[dict]:
    """`GET /configuracion/publica`: cualquier autenticado, solo claves `publico=True`."""
    repo = ConfiguracionParametroRepository(session)
    resultado = []
    for clave, definicion in REGISTRO_PARAMETROS.items():
        if not definicion.publico:
            continue
        guardado = repo.por_clave(clave)
        valor = guardado.valor if (guardado and guardado.valor) else definicion.valor_por_defecto
        resultado.append({"clave": clave, "valor": valor})
    return resultado
