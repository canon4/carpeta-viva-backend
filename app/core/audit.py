import uuid

from sqlalchemy.orm import Session

from app.modules.auditoria.models import AuditoriaAcceso


def registrar_acceso(
    session: Session,
    *,
    accion: str,
    usuario_id: uuid.UUID | None = None,
    recurso: str | None = None,
    menor_id: uuid.UUID | None = None,
    ip: str | None = None,
) -> None:
    """Auditoría de solo inserción: todo acceso a expedientes y eventos de sesión."""
    session.add(
        AuditoriaAcceso(
            usuario_id=usuario_id, accion=accion, recurso=recurso, menor_id=menor_id, ip=ip
        )
    )
    session.commit()
