"""Perfil con foto para todos los roles (ADR-0019).

Columnas nuevas, todas nulas, sin dato que migrar:
- `usuarios.nombres`/`apellidos`: nombre para roles sin tabla propia (coordinador/admin/auditor).
- `usuarios.foto_ref`: foto de perfil genérica para los 6 roles (ruta cifrada, ver
  `app/core/almacenamiento.py`).
- `hogar_red_apoyo.foto_ref`: una sola foto por contacto de red de apoyo.

Revision ID: 0014
Revises: 0013
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, Sequence[str], None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hogar_red_apoyo", sa.Column("foto_ref", sa.String(length=255), nullable=True))
    op.add_column("usuarios", sa.Column("nombres", sa.String(length=120), nullable=True))
    op.add_column("usuarios", sa.Column("apellidos", sa.String(length=120), nullable=True))
    op.add_column("usuarios", sa.Column("foto_ref", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("usuarios", "foto_ref")
    op.drop_column("usuarios", "apellidos")
    op.drop_column("usuarios", "nombres")
    op.drop_column("hogar_red_apoyo", "foto_ref")
