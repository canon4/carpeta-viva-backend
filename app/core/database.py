import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, create_engine, event, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


class UuidPk:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


_engine = None
_session_factory: sessionmaker[Session] | None = None


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
        if _engine.dialect.name == "postgresql":
            # Fuerza UTC en cada conexión nueva. Varias comparaciones de fecha (p. ej. `citas`
            # visita_vencida, RF9) hacen `columna_timestamptz < ahora_naive_utc` en SQL; sin esto,
            # PostgreSQL interpreta el valor naive según el `TimeZone` de sesión del servidor, que
            # no está garantizado en UTC (depende del contenedor/host), e introduciría un
            # desfase horario real sin que el código lo note.
            @event.listens_for(_engine, "connect")
            def _forzar_utc(dbapi_connection, connection_record):  # noqa: ARG001
                cursor = dbapi_connection.cursor()
                cursor.execute("SET TIME ZONE 'UTC'")
                cursor.close()

        _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session():
    get_engine()
    assert _session_factory is not None
    with _session_factory() as session:
        yield session
