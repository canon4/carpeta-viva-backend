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
    fuseki_url: str = "http://localhost:3030/ds"
    cors_origins: list[str] = ["http://localhost:4200"]
    archivos_dir: str = "./data/archivos"
    archivos_clave_maestra: str = ARCHIVOS_CLAVE_POR_DEFECTO
    # Límite de tamaño por archivo subido (RF2), para evitar que un usuario autenticado llene el
    # disco con cargas repetidas (DoS de almacenamiento). 25 MB cubre holgadamente fotos de
    # celular, PDFs e imágenes de documentos de identidad digitalizados.
    archivos_tamanio_maximo_bytes: int = 25 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
