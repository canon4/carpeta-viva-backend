"""alertas: configuración editable por admin (teléfono Policía de Infancia)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-13 00:00:00.000000

El teléfono de la Policía de Infancia y Adolescencia mostrado en la pantalla de emergencia de
evasión (ADR-0009, sección 1) era una variable de entorno fija (`POLICIA_INFANCIA_TELEFONO`):
cambiarlo exigía redesplegar. Se agrega una fila de configuración editable por `admin` en
tiempo de ejecución (`PUT /alertas/configuracion/telefono-policia-infancia`). Fila única
(`id=1`); si `telefono` es NULL, la aplicación sigue usando la variable de entorno como
respaldo (ver `app/modules/alertas/application.py`).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "configuracion_alertas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telefono_policia_infancia", sa.String(length=60), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actualizado_por", sa.Uuid(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_configuracion_alertas_fila_unica"),
    )
    op.execute("INSERT INTO configuracion_alertas (id, telefono_policia_infancia) VALUES (1, NULL)")


def downgrade() -> None:
    op.drop_table("configuracion_alertas")
