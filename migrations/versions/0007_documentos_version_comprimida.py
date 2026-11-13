"""documentos_versiones: agrega columna comprimida

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-13 00:00:00.000000

ADR-0011 (visor de documentos y compresión de versiones reemplazadas): cuando una versión de un
documento queda reemplazada por una nueva, y es una imagen, se recomprime antes de guardarla como
historial (para no acumular espacio en disco con copias en calidad completa que nadie vuelve a
necesitar). Esta columna registra si la copia guardada en `documentos_versiones` es la original
o una recompresión, para que el historial lo muestre con transparencia.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documentos_versiones",
        sa.Column("comprimida", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("documentos_versiones", "comprimida")
