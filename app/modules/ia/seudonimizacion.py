"""Asistente de IA: seudonimización de entidades conocidas (ADR-0010, sección 1.4).

Corrección obligatoria de la revisión de seguridad (punto 5): la sustitución de nombres no se
limita a las entidades del *contexto* de una consulta puntual (el menor preguntado, su madre,
sus profesionales): se construye un índice contra **todos** los nombres conocidos en las tablas
relevantes (`menores`, `menores_familiares`, `madres_sustitutas`, `profesionales`) antes de
armar el prompt, porque un fragmento recuperado puede mencionar por nombre a otra persona ya
modelada que no es parte de ese contexto (otro hermano, otra madre, otro profesional).

No se crea una tabla de pseudónimos persistente: el seudónimo es una función determinística del
`id` real ya existente y el mapa de sustitución vive solo en memoria durante la solicitud.

Límite documentado (sección 1.4, punto 5.2): un tercero mencionado en texto libre que NO tiene
fila en el sistema (p. ej. "la vecina Rosa dijo...") no se detecta aquí ni con los patrones de
`domain.py` — requiere una pasada de NER de personas, no implementada, y es requisito
bloqueante antes de activar `anonimizado=false` (ver `GET /ia/estado`).
"""
import re
import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.madres.models import MadreSustituta
from app.modules.menores.models import Menor, MenorFamiliar
from app.modules.profesionales.models import Profesional

from .domain import normalizar_nombre


def _pseudonimo(prefijo: str, entidad_id: uuid.UUID) -> str:
    return f"{prefijo}_{entidad_id.hex[:8].upper()}"


def construir_indice_entidades_conocidas(session: Session) -> dict[str, str]:
    """`nombre completo normalizado -> pseudónimo determinístico`, contra TODA la tabla, no solo
    el contexto de la consulta puntual (corrección obligatoria, sección 1.4 punto 5)."""
    indice: dict[str, str] = {}

    for menor in session.scalars(select(Menor)):
        nombre = normalizar_nombre(f"{menor.nombres} {menor.apellidos}")
        if nombre:
            indice[nombre] = _pseudonimo("MENOR", menor.id)

    for familiar in session.scalars(select(MenorFamiliar)):
        if familiar.nombres:
            nombre = normalizar_nombre(familiar.nombres)
            if nombre:
                indice[nombre] = _pseudonimo("FAMILIAR", familiar.id)

    for madre in session.scalars(select(MadreSustituta)):
        nombre = normalizar_nombre(f"{madre.nombres} {madre.apellidos}")
        if nombre:
            indice[nombre] = _pseudonimo("MADRE", madre.id)

    for profesional in session.scalars(select(Profesional)):
        nombre = normalizar_nombre(f"{profesional.nombres} {profesional.apellidos}")
        if nombre:
            indice[nombre] = _pseudonimo("PROFESIONAL", profesional.id)

    return indice


def _normalizar_preservando_longitud(texto: str) -> str:
    """Igual que `normalizar_nombre` (sin acentos, mayúsculas) pero sin colapsar espacios ni
    recortar bordes: cada carácter de salida corresponde exactamente al mismo índice en `texto`,
    para poder ubicar una coincidencia en la versión normalizada y sustituirla en el original."""
    salida = []
    for caracter in texto:
        base = "".join(c for c in unicodedata.normalize("NFD", caracter) if unicodedata.category(c) != "Mn")
        salida.append((base or caracter).upper())
    return "".join(salida)


def seudonimizar_nombres_conocidos(texto: str, indice: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Sustituye por coincidencia exacta de nombre completo (normalizando mayúsculas/acentos)
    contra `indice`, construido sobre TODOS los nombres conocidos (no solo el contexto de la
    pregunta). Nombres más largos primero, para que un nombre compuesto no quede parcialmente
    sustituido por el nombre de pila de otra persona que lo contenga como subcadena."""
    mapa_restitucion: dict[str, str] = {}
    resultado = texto
    for nombre_normalizado, pseudonimo in sorted(indice.items(), key=lambda kv: -len(kv[0])):
        if not nombre_normalizado:
            continue
        patron = re.compile(re.escape(nombre_normalizado).replace(r"\ ", r"\s+"))

        vista_normalizada = _normalizar_preservando_longitud(resultado)
        # Se busca la posición sobre la vista normalizada (misma longitud que `resultado`,
        # carácter a carácter) y se sustituye esa misma posición en el texto real, para
        # restituir luego el fragmento original con sus acentos/mayúsculas, no la vista en
        # mayúsculas usada solo para encontrar la coincidencia.
        nuevo = []
        cursor = 0
        contador = 0
        for match in patron.finditer(vista_normalizada):
            contador += 1
            marcador = pseudonimo if contador == 1 else f"{pseudonimo}_{contador}"
            mapa_restitucion[marcador] = resultado[match.start() : match.end()]
            nuevo.append(resultado[cursor : match.start()])
            nuevo.append(marcador)
            cursor = match.end()
        nuevo.append(resultado[cursor:])
        resultado = "".join(nuevo)
    return resultado, mapa_restitucion
