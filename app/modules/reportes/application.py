"""Reportes: Casos de uso (ADR-0010, sección 2).

Los cuatro niveles (general, zona, menor, madre) son agregados de solo lectura: se construyen
llamando a la capa de aplicación de cada módulo (`menores`, `asignaciones`, `documentos`,
`alertas`, `citas`, `inventario`, `alimentos`, `zonas_hogares`) con el `usuario` real que hace la
consulta, para que la autorización por fila/sección de cada módulo ya existente decida qué se
ve — este módulo no reimplementa esas reglas, solo agrega.

**Corrección obligatoria de seguridad (ADR-0010, sección 2, revisión de seguridad):**
`POST /reportes/exportar` congela en `filtros.secciones_incluidas` qué secciones sensibles
quedaron incluidas al generar; `GET /reportes/exportados/{id}/contenido` revalida la
autorización del nivel **con los permisos vigentes al momento de la descarga**, no con los que
existían al generar, y si el `menor_id` incluido se archivó después (sección 3), aplica la
misma regla de acceso que `archivo.obtener_estado` en vez de servir el archivo igual.

Las importaciones de otros módulos se hacen dentro de cada función para evitar ciclos entre
capas de aplicación hermanas (mismo patrón que `documentos`/`menores`).
"""
import csv
import io
import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core import almacenamiento
from app.core.audit import registrar_acceso
from app.core.errors import no_encontrado, prohibido
from app.modules.auth.domain import Rol

from .domain import SECCIONES_SENSIBLES
from .models import InformeGenerado
from .repository import InformeGeneradoRepository
from .schemas import (
    DocumentoResumen,
    ExportarRequest,
    ReporteAgregadoOut,
    ReporteMadreOut,
    ReporteMenorOut,
)


def _json_default(valor):
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return str(valor)


# ---------------------------------------------------------------------------
# Autorización por nivel
# ---------------------------------------------------------------------------

def _autorizado_general(usuario) -> bool:
    return usuario.rol in (Rol.ADMIN.value, Rol.AUDITOR.value, Rol.COORDINADOR.value)


def _zona_para_general(usuario) -> uuid.UUID | None:
    """ADR-0010, sección 2: coordinador que pide `general` recibe automáticamente el agregado
    de su propia zona (no la suma nacional)."""
    return usuario.zona_id if usuario.rol == Rol.COORDINADOR.value else None


def _autorizado_zona(usuario, zona_id: uuid.UUID) -> bool:
    rol = usuario.rol
    if rol in (Rol.ADMIN.value, Rol.AUDITOR.value):
        return True
    if rol == Rol.COORDINADOR.value:
        return usuario.zona_id is not None and usuario.zona_id == zona_id
    return False


def _autorizado_madre(session: Session, usuario, madre_id: uuid.UUID) -> tuple[bool, bool]:
    """Devuelve (autorizado, solo_agregado)."""
    rol = usuario.rol
    if rol == Rol.ADMIN.value:
        return True, False
    if rol == Rol.AUDITOR.value:
        return True, True
    if rol == Rol.MADRE.value:
        from app.modules.madres.application import madre_de_usuario

        propia = madre_de_usuario(session, usuario.id)
        return (propia is not None and propia.id == madre_id), False
    if rol == Rol.COORDINADOR.value:
        if usuario.zona_id is None:
            return False, False
        from app.modules.zonas_hogares.application import listar_hogares

        hogares_madre = [h for h in listar_hogares(session) if h.madre_id == madre_id]
        return any(h.zona_id == usuario.zona_id for h in hogares_madre), False
    return False, False


# ---------------------------------------------------------------------------
# Construcción de agregados (general/zona)
# ---------------------------------------------------------------------------

def _construir_agregado(session: Session, usuario, zona_id: uuid.UUID | None) -> ReporteAgregadoOut:
    from app.modules.alertas.application import listar_alertas
    from app.modules.alimentos.application import listar_alimentos
    from app.modules.asignaciones.application import listar_asignaciones_visibles
    from app.modules.documentos.application import listar_documentos
    from app.modules.menores.application import listar_menores
    from app.modules.zonas_hogares.application import listar_hogares

    menores = listar_menores(session, usuario, zona_id=zona_id)
    menor_ids = {m.id for m in menores}

    menores_por_estado: dict[str, int] = {}
    for m in menores:
        menores_por_estado[m.estado_actual] = menores_por_estado.get(m.estado_actual, 0) + 1

    hogares = listar_hogares(session, zona_id=zona_id)
    capacidad_total = sum(h.capacidad_maxima for h in hogares)

    vigentes = listar_asignaciones_visibles(session, usuario, zona_id=zona_id, estado="vigente")
    hogares_ocupados = {a.hogar_id for a in vigentes}

    documentos_pendientes = len(
        [
            d
            for d in listar_documentos(session, usuario, estado_flujo="en_revision")
            if d.menor_id in menor_ids
        ]
    )

    alertas_por_tipo: dict[str, int] = {}
    for a in listar_alertas(session, usuario, estado="activa"):
        if a.menor_id in menor_ids:
            alertas_por_tipo[a.tipo] = alertas_por_tipo.get(a.tipo, 0) + 1

    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    citas_vencidas = 0
    from app.modules.citas.application import listar_citas

    for c in listar_citas(session, usuario, estado="pendiente"):
        if c.menor_id in menor_ids:
            fh = c.fecha_hora.replace(tzinfo=None) if c.fecha_hora.tzinfo else c.fecha_hora
            if fh < ahora:
                citas_vencidas += 1

    alimentos_vencidos = 0
    for hogar in hogares:
        alimentos_vencidos += len(listar_alimentos(session, usuario, hogar.id, vencidos=True))

    return ReporteAgregadoOut(
        zona_id=zona_id,
        menores_por_estado=menores_por_estado,
        hogares_total=len(hogares),
        hogares_capacidad_total=capacidad_total,
        hogares_con_ocupacion_vigente=len(hogares_ocupados),
        documentos_pendientes_revision=documentos_pendientes,
        alertas_activas_por_tipo=alertas_por_tipo,
        citas_vencidas=citas_vencidas,
        alimentos_vencidos=alimentos_vencidos,
    )


def reporte_general(session: Session, usuario) -> ReporteAgregadoOut:
    if not _autorizado_general(usuario):
        registrar_acceso(session, accion="reporte_general_denegado", usuario_id=usuario.id)
        raise prohibido()
    if usuario.rol == Rol.COORDINADOR.value and usuario.zona_id is None:
        registrar_acceso(session, accion="reporte_general_denegado", usuario_id=usuario.id)
        raise prohibido()
    resultado = _construir_agregado(session, usuario, _zona_para_general(usuario))
    registrar_acceso(session, accion="reporte_general_consultado", usuario_id=usuario.id)
    return resultado


def reporte_zona(session: Session, usuario, zona_id: uuid.UUID) -> ReporteAgregadoOut:
    if not _autorizado_zona(usuario, zona_id):
        registrar_acceso(session, accion="reporte_zona_denegado", usuario_id=usuario.id, recurso=str(zona_id))
        raise prohibido()
    resultado = _construir_agregado(session, usuario, zona_id)
    registrar_acceso(session, accion="reporte_zona_consultado", usuario_id=usuario.id, recurso=str(zona_id))
    return resultado


# ---------------------------------------------------------------------------
# Reporte por menor
# ---------------------------------------------------------------------------

def reporte_menor(session: Session, usuario, menor_id: uuid.UUID) -> ReporteMenorOut:
    from app.modules.alertas.application import listar_alertas
    from app.modules.asignaciones.application import vigente_de_menor
    from app.modules.citas.application import listar_citas
    from app.modules.documentos.application import listar_documentos, listar_reportes
    from app.modules.menores.application import obtener_menor, tiene_permiso_seccion

    menor = obtener_menor(session, usuario, menor_id)  # ya aplica puede_ver_menor + auditoría

    vigente = vigente_de_menor(session, menor_id)

    documentos = listar_documentos(session, usuario, menor_id=menor_id)
    por_categoria: dict[str, int] = {}
    for d in documentos:
        por_categoria[d.categoria] = por_categoria.get(d.categoria, 0) + 1

    reportes = listar_reportes(session, usuario, menor_id=menor_id)
    por_tipo: dict[str, int] = {}
    for r in reportes:
        por_tipo[r.tipo_reporte] = por_tipo.get(r.tipo_reporte, 0) + 1

    alertas_activas = len([a for a in listar_alertas(session, usuario, menor_id=menor_id) if a.estado == "activa"])

    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    citas_proximas = 0
    for c in listar_citas(session, usuario, menor_id=menor_id, estado="pendiente"):
        fh = c.fecha_hora.replace(tzinfo=None) if c.fecha_hora.tzinfo else c.fecha_hora
        if fh >= ahora:
            citas_proximas += 1

    secciones_sin_acceso = [s for s in SECCIONES_SENSIBLES if not tiene_permiso_seccion(session, usuario, menor_id, s)]

    resultado = ReporteMenorOut(
        menor_id=menor_id,
        estado_actual=menor.estado_actual,
        asignacion_vigente_hogar_id=vigente.hogar_id if vigente is not None else None,
        documentos_por_categoria=por_categoria,
        documentos_visibles=[DocumentoResumen.model_validate(d) for d in documentos],
        reportes_por_tipo=por_tipo,
        alertas_activas=alertas_activas,
        citas_proximas=citas_proximas,
        secciones_sin_acceso=secciones_sin_acceso,
    )
    registrar_acceso(session, accion="reporte_menor_consultado", usuario_id=usuario.id, menor_id=menor_id)
    return resultado


# ---------------------------------------------------------------------------
# Reporte por madre
# ---------------------------------------------------------------------------

def reporte_madre(session: Session, usuario, madre_id: uuid.UUID) -> ReporteMadreOut:
    from app.modules.alertas.application import listar_alertas
    from app.modules.alimentos.application import listar_alimentos
    from app.modules.asignaciones.application import listar_asignaciones_visibles
    from app.modules.documentos.application import listar_documentos
    from app.modules.inventario.application import listar_items
    from app.modules.madres.application import obtener_madre
    from app.modules.zonas_hogares.application import listar_hogares

    madre = obtener_madre(session, madre_id)  # 404 si no existe

    autorizado, solo_agregado = _autorizado_madre(session, usuario, madre_id)
    if not autorizado:
        registrar_acceso(session, accion="reporte_madre_denegado", usuario_id=usuario.id, recurso=str(madre_id))
        raise prohibido()

    hogares = [h for h in listar_hogares(session) if h.madre_id == madre_id]

    menores_asignados: list[uuid.UUID] = []
    alertas_activas = 0
    documentos_por_estado: dict[str, int] = {}
    for hogar in hogares:
        vigentes = listar_asignaciones_visibles(session, usuario, hogar_id=hogar.id, estado="vigente")
        for asignacion in vigentes:
            menores_asignados.append(asignacion.menor_id)
            alertas_activas += len(
                [a for a in listar_alertas(session, usuario, menor_id=asignacion.menor_id) if a.estado == "activa"]
            )
            for doc in listar_documentos(session, usuario, menor_id=asignacion.menor_id):
                if madre.usuario_id is not None and doc.creado_por == madre.usuario_id:
                    documentos_por_estado[doc.estado_flujo] = documentos_por_estado.get(doc.estado_flujo, 0) + 1

    inventario_total = sum(len(listar_items(session, usuario, hogar.id)) for hogar in hogares)
    alimentos_vencidos = sum(len(listar_alimentos(session, usuario, hogar.id, vencidos=True)) for hogar in hogares)

    resultado = ReporteMadreOut(
        madre_id=madre_id,
        hogares=[h.id for h in hogares],
        menores_asignados=menores_asignados,
        documentos_creados_por_ella_por_estado=documentos_por_estado,
        alertas_activas=alertas_activas,
        inventario_items=inventario_total,
        alimentos_vencidos=alimentos_vencidos,
        solo_agregado=solo_agregado,
    )
    registrar_acceso(session, accion="reporte_madre_consultado", usuario_id=usuario.id, recurso=str(madre_id))
    return resultado


# ---------------------------------------------------------------------------
# Exportación
# ---------------------------------------------------------------------------

def _generar_contenido(nivel: str, cuerpo, formato: str, filtros: dict) -> bytes:
    if formato == "json":
        datos = cuerpo.model_dump() if hasattr(cuerpo, "model_dump") else cuerpo
        return json.dumps(datos, default=_json_default, ensure_ascii=False, indent=2).encode("utf-8")

    datos = cuerpo.model_dump() if hasattr(cuerpo, "model_dump") else cuerpo
    filas: list[tuple[str, str]] = []
    for clave, valor in datos.items():
        if isinstance(valor, dict):
            for subclave, subvalor in valor.items():
                filas.append((f"{clave}.{subclave}", str(subvalor)))
        elif isinstance(valor, list):
            filas.append((clave, "; ".join(str(v) for v in valor)))
        else:
            filas.append((clave, str(valor)))

    if formato == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["campo", "valor"])
        writer.writerows(filas)
        return buffer.getvalue().encode("utf-8")

    if formato == "pdf":
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, f"Reporte Carpeta Viva - nivel {nivel}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            pdf.epw,
            8,
            f"Filtros: {json.dumps(filtros, default=_json_default, ensure_ascii=False)}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(2)
        for campo, valor in filas:
            texto = f"{campo}: {valor}"
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(pdf.epw, 7, texto, new_x="LMARGIN", new_y="NEXT")
        return bytes(pdf.output())

    raise ValueError(f"Formato no soportado: {formato}")


def exportar_informe(session: Session, usuario, datos: ExportarRequest) -> InformeGenerado:
    from .domain import FORMATOS, NIVELES

    if datos.nivel not in NIVELES:
        raise ValueError(f"nivel debe ser uno de {NIVELES}")
    if datos.formato not in FORMATOS:
        raise ValueError(f"formato debe ser uno de {FORMATOS}")

    filtros: dict = {}
    secciones_incluidas: list[str] = []

    if datos.nivel == "general":
        cuerpo = reporte_general(session, usuario)
        filtros["zona_id"] = str(cuerpo.zona_id) if cuerpo.zona_id else None
    elif datos.nivel == "zona":
        if datos.zona_id is None:
            raise ValueError("zona_id es obligatorio para nivel=zona")
        cuerpo = reporte_zona(session, usuario, datos.zona_id)
        filtros["zona_id"] = str(datos.zona_id)
    elif datos.nivel == "menor":
        if datos.menor_id is None:
            raise ValueError("menor_id es obligatorio para nivel=menor")
        cuerpo = reporte_menor(session, usuario, datos.menor_id)
        filtros["menor_id"] = str(datos.menor_id)
        secciones_incluidas = [s for s in SECCIONES_SENSIBLES if s not in cuerpo.secciones_sin_acceso]
    elif datos.nivel == "madre":
        if datos.madre_id is None:
            raise ValueError("madre_id es obligatorio para nivel=madre")
        cuerpo = reporte_madre(session, usuario, datos.madre_id)
        filtros["madre_id"] = str(datos.madre_id)
    else:
        raise ValueError("nivel inválido")

    # Corrección obligatoria de seguridad (ADR-0010, sección 2): se congela qué secciones
    # sensibles quedaron incluidas, para revalidar exactamente eso al descargar.
    filtros["secciones_incluidas"] = secciones_incluidas

    contenido = _generar_contenido(datos.nivel, cuerpo, datos.formato, filtros)
    referencia, _hash = almacenamiento.guardar(usuario.id, uuid.uuid4(), 1, contenido)

    informe = InformeGenerado(
        usuario_id=usuario.id,
        nivel=datos.nivel,
        filtros=filtros,
        formato=datos.formato,
        referencia_archivo=referencia,
    )
    informe = InformeGeneradoRepository(session).crear(informe)
    registrar_acceso(session, accion="informe_exportado", usuario_id=usuario.id, recurso=str(informe.id))
    return informe


def listar_exportados(session: Session, usuario) -> list[InformeGenerado]:
    repo = InformeGeneradoRepository(session)
    if usuario.rol in (Rol.ADMIN.value, Rol.AUDITOR.value):
        resultado = repo.listar_todos()
    else:
        resultado = repo.listar_por_usuario(usuario.id)
    registrar_acceso(session, accion="informes_exportados_listados", usuario_id=usuario.id)
    return resultado


def _informe_o_404(session: Session, informe_id: uuid.UUID) -> InformeGenerado:
    informe = InformeGeneradoRepository(session).por_id(informe_id)
    if informe is None:
        raise no_encontrado("Informe no encontrado")
    return informe


def _autorizado_descarga_ahora(session: Session, usuario, informe: InformeGenerado) -> bool:
    """Revalidación obligatoria (ADR-0010, sección 2): autorización del nivel con los permisos
    **vigentes ahora**, no los que existían al generar. `auditor` nunca descarga contenido
    (solo metadatos vía `listar_exportados`)."""
    if usuario.rol == Rol.AUDITOR.value:
        return False

    filtros = informe.filtros or {}
    nivel = informe.nivel

    if nivel == "general":
        if not _autorizado_general(usuario):
            return False
        if usuario.rol == Rol.COORDINADOR.value:
            # Corrección de seguridad: el nivel "general" generado por un coordinador queda
            # acotado a su zona (filtros["zona_id"]), pero sin este chequeo cualquier otro
            # coordinador podría descargarlo igual (la revalidación de arriba solo miraba el
            # rol, no si era SU zona) — mismo patrón ya aplicado a los niveles zona/menor.
            zona_id_str = filtros.get("zona_id")
            if not zona_id_str or usuario.zona_id is None or str(usuario.zona_id) != zona_id_str:
                return False
        return True

    if nivel == "zona":
        zona_id_str = filtros.get("zona_id")
        if not zona_id_str:
            return False
        return _autorizado_zona(usuario, uuid.UUID(zona_id_str))

    if nivel == "menor":
        menor_id_str = filtros.get("menor_id")
        if not menor_id_str:
            return False
        menor_id = uuid.UUID(menor_id_str)

        from app.modules.archivo.application import autorizado_para_ver_archivado, esta_archivado
        from app.modules.menores.application import puede_ver_menor, tiene_permiso_seccion

        if esta_archivado(session, menor_id):
            # El expediente se archivó después de exportado (sección 3): mismo criterio de
            # acceso que el estado de archivo (coordinador de esa zona/admin/auditor; auditor ya
            # excluido arriba).
            return autorizado_para_ver_archivado(session, usuario, menor_id)

        if not puede_ver_menor(session, usuario, menor_id):
            return False
        for seccion in filtros.get("secciones_incluidas", []):
            if not tiene_permiso_seccion(session, usuario, menor_id, seccion):
                return False
        return True

    if nivel == "madre":
        madre_id_str = filtros.get("madre_id")
        if not madre_id_str:
            return False
        autorizado, _solo_agregado = _autorizado_madre(session, usuario, uuid.UUID(madre_id_str))
        return autorizado

    return False


def obtener_contenido_exportado(session: Session, usuario, informe_id: uuid.UUID) -> tuple[InformeGenerado, bytes]:
    informe = _informe_o_404(session, informe_id)
    if not _autorizado_descarga_ahora(session, usuario, informe):
        registrar_acceso(
            session, accion="informe_descarga_denegada", usuario_id=usuario.id, recurso=str(informe.id)
        )
        raise prohibido()
    if informe.referencia_archivo is None:
        raise no_encontrado("Este informe no tiene archivo asociado")
    contenido = almacenamiento.leer(informe.referencia_archivo)
    registrar_acceso(session, accion="informe_descargado", usuario_id=usuario.id, recurso=str(informe.id))
    return informe, contenido
