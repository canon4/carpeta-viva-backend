"""Configuración administrable: registro en código de qué catálogos y parámetros existen
(ADR-0013, módulo transversal T4).

Este registro NO contiene lógica de negocio propia: solo le dice al `admin` qué grupos de
catálogo y qué claves de parámetro puede administrar, cruzado con lo que ya hay guardado en
`catalogos_opciones`/`configuracion_sistema`. La lógica de negocio que usa estos valores (p.ej.
qué sección de permiso exige una categoría documental) sigue viviendo en el módulo dueño
(`documentos/domain.py`), nunca aquí (sección 2 y 6 del ADR).
"""
from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class GrupoCatalogoDef:
    etiqueta: str
    descripcion: str
    # ADR-0013, sección 5.1 (revisión de seguridad): grupos cuyas opciones determinan una
    # sección de permiso (hoy solo categoría documental de menor) exigen `seccion_acceso` al
    # crear la opción, inmutable después. Un grupo nuevo sin lógica de permisos asociada se
    # registra con `con_seccion_acceso=False`.
    con_seccion_acceso: bool = False


@dataclass(frozen=True)
class ParametroDef:
    tipo: str  # "str" | "int" | "bool" — casteo validado al escribir (PUT /parametros/{clave})
    valor_por_defecto: str
    descripcion: str
    publico: bool = False
    grupo: str | None = None


# Conjunto cerrado de secciones de permiso (ADR-0013, sección 5.1). Nunca texto libre: una fila
# corrupta o un valor no reconocido en runtime cae a `None` (visibilidad básica), nunca a una
# sección sensible por accidente.
SECCIONES_VALIDAS = ("familia", "salud", "psicosocial")


GRUPOS_CATALOGO: dict[str, GrupoCatalogoDef] = {
    "categoria_documento_menor": GrupoCatalogoDef(
        etiqueta="Categorías documentales de menor",
        descripcion=(
            "Categorías para clasificar documentos del expediente de un NNA (ADR-0008 sección 2, "
            "provisionales según ADR-0008). Cada opción fija su sección de acceso al crearse."
        ),
        con_seccion_acceso=True,
    ),
    "categoria_documento_hogar": GrupoCatalogoDef(
        etiqueta="Categorías documentales de hogar",
        descripcion="Categorías para clasificar documentos propios del hogar sustituto (no del NNA).",
        con_seccion_acceso=False,
    ),
}


REGISTRO_PARAMETROS: dict[str, ParametroDef] = {
    "telefono_policia_infancia": ParametroDef(
        tipo="str",
        # Constante actual (ADR-0013, sección 7.4): la misma que ya usaba `configuracion_alertas`
        # como respaldo cuando no hay valor editado por `admin` (variable de entorno
        # `POLICIA_INFANCIA_TELEFONO`, ver app/core/config.py).
        valor_por_defecto=get_settings().policia_infancia_telefono,
        descripcion=(
            "Teléfono de la Policía de Infancia y Adolescencia mostrado en la pantalla de "
            "emergencia de evasión (ADR-0009)."
        ),
        publico=False,
    ),
    "nombre_operador": ParametroDef(
        tipo="str",
        valor_por_defecto="",
        descripcion="Nombre del operador/fundación, mostrado en pantallas institucionales.",
        publico=True,
    ),
    "contacto_operador": ParametroDef(
        tipo="str",
        valor_por_defecto="",
        descripcion="Dato de contacto institucional del operador (teléfono o correo).",
        publico=True,
    ),
}
