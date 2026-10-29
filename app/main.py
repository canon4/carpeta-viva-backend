from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import JWT_SECRET_POR_DEFECTO, get_settings
from app.modules.registry import routers

VERSION = "0.1.0"


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.environment == "production" and settings.jwt_secret == JWT_SECRET_POR_DEFECTO:
        raise RuntimeError("JWT_SECRET debe definirse en producción")

    app = FastAPI(
        title=settings.app_name,
        version=VERSION,
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get(f"{settings.api_prefix}/health", tags=["Sistema"], summary="Estado del servicio")
    def health() -> dict[str, str]:
        return {"estado": "ok", "version": VERSION}

    for router in routers():
        app.include_router(router, prefix=settings.api_prefix)
    return app


app = create_app()
