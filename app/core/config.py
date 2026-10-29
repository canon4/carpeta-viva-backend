from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

JWT_SECRET_POR_DEFECTO = "cambiar-en-produccion-clave-solo-de-desarrollo"


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


@lru_cache
def get_settings() -> Settings:
    return Settings()
