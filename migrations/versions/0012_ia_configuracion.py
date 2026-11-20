"""configuración del proveedor de IA editable por el admin

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-20 00:00:00.000000

ADR-0017: tabla `ia_configuracion` (una fila) con proveedor, modelo y la clave de API cifrada
con la clave maestra (`app/core/secretos.py`). La clave nunca se devuelve por la API.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ia_configuracion",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("proveedor", sa.String(length=50), nullable=False),
        sa.Column("modelo", sa.String(length=100), nullable=False),
        sa.Column("api_key_cifrada", sa.Text(), nullable=True),
        sa.Column("api_key_sufijo", sa.String(length=8), nullable=True),
        sa.Column("actualizado_por", sa.Uuid(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ia_configuracion")
