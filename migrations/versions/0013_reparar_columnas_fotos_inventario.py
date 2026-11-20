"""Repara `inventario_item_fotos` en bases que aplicaron una versión temprana de la 0010.

La 0010 se amplió con `declaracion_sin_menores` y `oculta` (revisión de seguridad, ADR-0014)
después de haberse aplicado en el servidor de despliegue. Alembic la daba por aplicada, así que
esas columnas nunca se crearon allí y cualquier consulta de fotos de inventario fallaba con
`UndefinedColumn`. Esta migración agrega solo las columnas que falten; en bases correctas no
hace nada.

Revision ID: 0013
Revises: 0012
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLA = "inventario_item_fotos"
COLUMNAS = (
    ("declaracion_sin_menores", sa.true()),
    ("oculta", sa.false()),
)


def _existentes() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLA)}


def upgrade() -> None:
    existentes = _existentes()
    for nombre, por_defecto in COLUMNAS:
        if nombre not in existentes:
            op.add_column(TABLA, sa.Column(nombre, sa.Boolean(), server_default=por_defecto, nullable=False))


def downgrade() -> None:
    # Las columnas pertenecen a la 0010; bajar de la 0013 no debe quitarlas.
    pass
