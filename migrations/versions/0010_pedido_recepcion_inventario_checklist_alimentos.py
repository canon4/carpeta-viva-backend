"""pedido/recepción en inventario; checklist reutilizable en alimentos

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-14 00:00:00.000000

ADR-0014: separa pedido (coordinador) de recepción (madre/admin) en Inventario del Hogar, y
agrega un checklist reutilizable para Control de Alimentos.

- `inventario_items.recibido`: ítems existentes se migran con `recibido=true` (se asume que ya
  estaban físicamente en el hogar, sección 3 del ADR).
- `inventario_item_fotos`: evidencia fotográfica de la recepción, cifrada igual que `documentos`
  (ADR-0008); sin versionado. Incluye `declaracion_sin_menores` (obligatoria, auditable) y
  `oculta` (remediación admin-only), incorporadas en la revisión de `seguridad` de la sección 2.1
  del ADR antes de que esta migración se desplegara en ningún entorno real; por eso se agregan
  aquí mismo en vez de en una migración `0011` aparte.
- `alimentos_checklist_items`: el "producto del mercado" reutilizable.
- `alimentos_items.checklist_item_id`: nullable, apunta al producto del checklist si la compra
  viene de ahí.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- inventario_items: recibido ---
    op.add_column(
        "inventario_items",
        sa.Column("recibido", sa.Boolean(), server_default=sa.true(), nullable=False),
    )

    # --- inventario_item_fotos ---
    op.create_table(
        "inventario_item_fotos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("referencia_archivo", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("tamanio_bytes", sa.Integer(), nullable=False),
        sa.Column("subido_por", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("declaracion_sin_menores", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("oculta", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["inventario_items.id"]),
        sa.ForeignKeyConstraint(["subido_por"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventario_item_fotos_item_id"), "inventario_item_fotos", ["item_id"], unique=False)

    # --- alimentos_checklist_items ---
    op.create_table(
        "alimentos_checklist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hogar_id", sa.Uuid(), nullable=False),
        sa.Column("descripcion", sa.String(length=255), nullable=False),
        sa.Column("perecedero", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("unidad_por_defecto", sa.String(length=20), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("creado_por", sa.Uuid(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["hogar_id"], ["hogares_sustitutos.id"]),
        sa.ForeignKeyConstraint(["creado_por"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alimentos_checklist_items_hogar_id"), "alimentos_checklist_items", ["hogar_id"], unique=False)

    # --- alimentos_items: checklist_item_id ---
    op.add_column("alimentos_items", sa.Column("checklist_item_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_alimentos_items_checklist_item_id",
        "alimentos_items",
        "alimentos_checklist_items",
        ["checklist_item_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_alimentos_items_checklist_item_id", "alimentos_items", type_="foreignkey")
    op.drop_column("alimentos_items", "checklist_item_id")

    op.drop_index(op.f("ix_alimentos_checklist_items_hogar_id"), table_name="alimentos_checklist_items")
    op.drop_table("alimentos_checklist_items")

    op.drop_index(op.f("ix_inventario_item_fotos_item_id"), table_name="inventario_item_fotos")
    op.drop_table("inventario_item_fotos")

    op.drop_column("inventario_items", "recibido")
