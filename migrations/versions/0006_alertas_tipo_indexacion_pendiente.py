"""alertas: agrega tipo indexacion_pendiente

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-04 00:00:00.000000

Corrección de seguridad de ADR-0010 (sección 1.3): la indexación de IA en segundo plano
(OCR + clasificación + embeddings) puede fallar o perderse a medias; sin una señal visible,
un documento puede quedar sin indexar indefinidamente sin que nadie lo note (el usuario
pregunta, el sistema responde "no encontré información" y nadie distingue si es porque el
dato no existe o porque la tarea se perdió). Se agrega `tipo=indexacion_pendiente` al
`CheckConstraint` de `alertas.tipo` (ya creado en la migración 0004), reutilizando el mecanismo
de alertas existente en vez de construir uno nuevo.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIPOS_ANTERIOR = ("evasion", "visita_vencida", "documento_faltante")
TIPOS_NUEVO = ("evasion", "visita_vencida", "documento_faltante", "indexacion_pendiente")


def upgrade() -> None:
    op.drop_constraint("ck_alertas_tipo", "alertas", type_="check")
    op.create_check_constraint(
        "ck_alertas_tipo", "alertas", "tipo IN (" + ", ".join(f"'{t}'" for t in TIPOS_NUEVO) + ")"
    )


def downgrade() -> None:
    op.drop_constraint("ck_alertas_tipo", "alertas", type_="check")
    op.create_check_constraint(
        "ck_alertas_tipo", "alertas", "tipo IN (" + ", ".join(f"'{t}'" for t in TIPOS_ANTERIOR) + ")"
    )
