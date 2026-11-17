from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

JWT_SECRET_POR_DEFECTO = "cambiar-en-produccion-clave-solo-de-desarrollo"
# Clave Fernet de solo-desarrollo (ADR-0008, sección 1): nunca usar en producción.
# Mismo patrón que JWT_SECRET_POR_DEFECTO; app/main.py debe rechazar el arranque en
# producción si ARCHIVOS_CLAVE_MAESTRA sigue en este valor.
ARCHIVOS_CLAVE_POR_DEFECTO = "Y2xhdmUtZmVybmV0LVNPTE8tZGV2LW5vLXVzYXItWCE="


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Carpeta Viva API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://carpeta:carpeta@localhost:5432/carpeta_viva"
    jwt_secret: str = JWT_SECRET_POR_DEFECTO
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    # Bloqueo temporal tras intentos fallidos de inicio de sesión (RF0.5, HU04).
    login_max_intentos: int = 5
    login_bloqueo_minutos: int = 15
    # Política mínima de contraseña al cambiarla (RF0.4, HU03).
    password_longitud_minima: int = 10
    fuseki_url: str = "http://localhost:3030/ds"
    cors_origins: list[str] = ["http://localhost:4200"]
    archivos_dir: str = "./data/archivos"
    archivos_clave_maestra: str = ARCHIVOS_CLAVE_POR_DEFECTO
    # Límite de tamaño por archivo subido (RF2), para evitar que un usuario autenticado llene el
    # disco con cargas repetidas (DoS de almacenamiento). 25 MB cubre holgadamente fotos de
    # celular, PDFs e imágenes de documentos de identidad digitalizados.
    archivos_tamanio_maximo_bytes: int = 25 * 1024 * 1024
    # Número de la Policía de Infancia y Adolescencia mostrado en la pantalla de evasión
    # (ADR-0009, sección 1): un solo operador/municipio hoy, no se migra a tabla todavía.
    policia_infancia_telefono: str = "cambiar-numero-real"

    # Asistente de IA (ADR-0010, sección 1.6): proveedor/modelo del LLM externo de generación,
    # intercambiable detrás de `ProveedorLLM` (`app/core/ia_llm.py`). La clave nunca tiene un
    # valor real por defecto; sin ella, `AnthropicProveedorLLM` falla explícitamente al llamar,
    # no al arrancar (para no bloquear el resto de la API en desarrollo sin clave).
    ia_llm_proveedor: str = "anthropic"
    # Verificado en platform.claude.com (nov. 2026): modelo más económico/rápido de la familia
    # Claude vigente (desde US$0.10/MTok de entrada, US$0.50/MTok de salida); revisar de nuevo
    # si Anthropic publica una familia más nueva/barata antes de producción.
    ia_llm_modelo: str = "claude-haiku-5-5"
    anthropic_api_key: str | None = None
    # Clave del adaptador Groq (ia_llm.py), alternativa a Anthropic. Solo se usa si
    # ia_llm_proveedor="groq"; nunca tiene valor real por defecto, igual que la de Anthropic.
    groq_api_key: str | None = None
    # Modelo de embeddings local (ADR-0010, sección 1.3): multilingüe, 384 dimensiones, sin
    # llamada externa. Versionado en `modelo_embedding` de `fragmentos_documento` como
    # "<nombre>@<version>" para poder reindexar todo si cambia.
    ia_embeddings_modelo: str = "intfloat/multilingual-e5-small"
    ia_embeddings_version: str = "1"
    # Seudonimización (ADR-0010, sección 1.4 + revisión de seguridad): activa por defecto.
    # Pasar a `false` requiere la pasada de NER de personas (pendiente, no implementada) y
    # habilitación explícita de `admin`/`seguridad` con contrato de tratamiento (ADR-0002
    # punto 4) — hoy solo hay datos sintéticos, así que esto no bloquea el prototipo, pero el
    # valor por defecto nunca debe cambiarse sin ese requisito.
    ia_anonimizado_por_defecto: bool = True
    # Indexación automática en segundo plano al guardar documento/versión (sección 1.3). Se
    # puede desactivar por configuración (p. ej. en pruebas de otros módulos que no necesitan
    # ejercitar el pipeline de IA) sin tocar el resto del sistema.
    ia_indexar_automaticamente: bool = True
    # Umbral para la alerta `indexacion_pendiente` (revisión de seguridad, sección 1.3): un
    # documento/reporte sin fragmentos indexados por más de este tiempo genera alerta.
    ia_indexacion_pendiente_umbral_minutos: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
