"""Proveedor de LLM externo intercambiable (ADR-0010, sección 1.6).

El resto del módulo `ia` (RAG, resumen, redacción) depende solo de `ProveedorLLM`, nunca del
SDK de un proveedor concreto directamente. `AnthropicProveedorLLM` es la primera implementación
(decisión de Diego); cambiar de proveedor SaaS o apuntar a un modelo propio en el futuro es
agregar un adaptador nuevo, sin tocar el resto del sistema. El proveedor/modelo activos se
seleccionan por configuración (`IA_LLM_PROVEEDOR`, `IA_LLM_MODELO`), expuestos (sin la clave) en
`GET /ia/estado`.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

from .config import get_settings


@dataclass(frozen=True)
class RespuestaLLM:
    texto: str
    modelo: str
    proveedor: str


class ProveedorLLMNoDisponible(Exception):
    """El proveedor configurado no se pudo invocar (sin clave, error de red, error de la API)."""


class ProveedorLLM(ABC):
    """Interfaz única de generación. Un adaptador concreto por proveedor (ADR-0010, sección 1.6)."""

    nombre: str

    @abstractmethod
    def generar(self, prompt: str, *, contexto: str, instrucciones_sistema: str) -> RespuestaLLM:
        """Genera una respuesta en lenguaje natural a partir de `prompt` (la pregunta o la
        instrucción de redacción) y `contexto` (los fragmentos recuperados y seudonimizados, ya
        armados como texto). `instrucciones_sistema` fija las reglas que la IA nunca debe romper
        (citar, no inventar, no decidir sobre el NNA — ADR-0002)."""


class AnthropicProveedorLLM(ProveedorLLM):
    """Adaptador concreto sobre la API SaaS de Anthropic (Claude), vía el SDK oficial `anthropic`."""

    nombre = "anthropic"

    def __init__(self, modelo: str, api_key: str | None):
        self.modelo = modelo
        self._api_key = api_key

    def generar(self, prompt: str, *, contexto: str, instrucciones_sistema: str) -> RespuestaLLM:
        if not self._api_key:
            raise ProveedorLLMNoDisponible(
                "ANTHROPIC_API_KEY no está configurada; defínala en el entorno (nunca en el repositorio)."
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise ProveedorLLMNoDisponible("El paquete 'anthropic' no está instalado") from exc

        cliente = anthropic.Anthropic(api_key=self._api_key)
        try:
            mensaje = cliente.messages.create(
                model=self.modelo,
                max_tokens=1024,
                system=instrucciones_sistema,
                messages=[{"role": "user", "content": f"{contexto}\n\n---\n\n{prompt}"}],
            )
        except Exception as exc:  # noqa: BLE001 - cualquier error de red/API se trata igual: no disponible
            raise ProveedorLLMNoDisponible(f"Error llamando a la API de Anthropic: {exc}") from exc

        texto = "".join(bloque.text for bloque in mensaje.content if getattr(bloque, "type", None) == "text")
        return RespuestaLLM(texto=texto, modelo=self.modelo, proveedor=self.nombre)


class GroqProveedorLLM(ProveedorLLM):
    """Adaptador concreto sobre la API SaaS de Groq, vía su SDK oficial `groq` (interfaz de
    chat compatible con el formato de OpenAI: lista de mensajes con roles)."""

    nombre = "groq"

    def __init__(self, modelo: str, api_key: str | None):
        self.modelo = modelo
        self._api_key = api_key

    def generar(self, prompt: str, *, contexto: str, instrucciones_sistema: str) -> RespuestaLLM:
        if not self._api_key:
            raise ProveedorLLMNoDisponible(
                "GROQ_API_KEY no está configurada; defínala en el entorno (nunca en el repositorio)."
            )
        try:
            import groq
        except ImportError as exc:  # pragma: no cover
            raise ProveedorLLMNoDisponible("El paquete 'groq' no está instalado") from exc

        cliente = groq.Groq(api_key=self._api_key)
        try:
            respuesta = cliente.chat.completions.create(
                model=self.modelo,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": instrucciones_sistema},
                    {"role": "user", "content": f"{contexto}\n\n---\n\n{prompt}"},
                ],
            )
        except Exception as exc:  # noqa: BLE001 - cualquier error de red/API se trata igual: no disponible
            raise ProveedorLLMNoDisponible(f"Error llamando a la API de Groq: {exc}") from exc

        texto = respuesta.choices[0].message.content or ""
        return RespuestaLLM(texto=texto, modelo=self.modelo, proveedor=self.nombre)


def construir_proveedor_llm(proveedor: str, modelo: str) -> ProveedorLLM:
    """Fábrica por nombre de proveedor (configuración). Agregar un proveedor nuevo es agregar
    una rama aquí y una clase nueva, sin tocar `ia.application`."""
    if proveedor == "anthropic":
        return AnthropicProveedorLLM(modelo=modelo, api_key=get_settings().anthropic_api_key)
    if proveedor == "groq":
        return GroqProveedorLLM(modelo=modelo, api_key=get_settings().groq_api_key)
    raise ValueError(f"Proveedor de LLM no soportado: {proveedor!r}")


@lru_cache
def obtener_proveedor_llm() -> ProveedorLLM:
    """Proveedor activo según configuración (`IA_LLM_PROVEEDOR`/`IA_LLM_MODELO`). `ia.application`
    depende de esta función (y de `ProveedorLLM`), nunca del SDK concreto."""
    settings = get_settings()
    return construir_proveedor_llm(settings.ia_llm_proveedor, settings.ia_llm_modelo)
