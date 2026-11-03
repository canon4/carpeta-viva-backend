"""documentos: metadatos de archivo, flujo de aprobacion y tabla de versiones

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03 00:00:00.000000

Ver docs/adr/0008-gestion-documental-almacenamiento-cifrado-y-flujo.md
(seccion 5) para el detalle. Esta migracion solo crea/altera esquema;
los modelos SQLAlchemy correspondientes los agrega el agente backend
por separado.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORIAS = (
    "identidad", "salud", "psicosocial", "educacion",
    "familia_red_apoyo", "actas_traslados", "madre_habilitacion", "otros",
)
ESTADOS_FLUJO = ("borrador", "en_revision", "aprobado", "devuelto")


def upgrade() -> None:
    """Upgrade schema."""
    # --- documentos: columnas nuevas ---
    op.add_column('documentos', sa.Column('nombre_original', sa.String(length=255), nullable=False, server_default='desconocido'))
    op.add_column('documentos', sa.Column('mime_type', sa.String(length=100), nullable=False, server_default='application/octet-stream'))
    op.add_column('documentos', sa.Column('tamanio_bytes', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('documentos', 'nombre_original', server_default=None)
    op.alter_column('documentos', 'mime_type', server_default=None)
    op.alter_column('documentos', 'tamanio_bytes', server_default=None)
    op.add_column('documentos', sa.Column('revisado_por', sa.Uuid(), nullable=True))
    op.add_column('documentos', sa.Column('revisado_en', sa.DateTime(timezone=True), nullable=True))
    op.add_column('documentos', sa.Column('motivo_devolucion', sa.String(length=255), nullable=True))
    op.create_foreign_key(
        op.f('fk_documentos_revisado_por_usuarios'), 'documentos', 'usuarios',
        ['revisado_por'], ['id'],
    )
    op.create_check_constraint(
        'ck_documentos_categoria',
        'documentos',
        "categoria IN (" + ", ".join(f"'{c}'" for c in CATEGORIAS) + ")",
    )
    op.create_check_constraint(
        'ck_documentos_estado_flujo',
        'documentos',
        "estado_flujo IN (" + ", ".join(f"'{e}'" for e in ESTADOS_FLUJO) + ")",
    )
    op.create_index(
        op.f('ix_documentos_menor_id_categoria'), 'documentos', ['menor_id', 'categoria'], unique=False,
    )

    # --- documentos_versiones ---
    op.create_table(
        'documentos_versiones',
        sa.Column('documento_id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('referencia_archivo', sa.String(length=255), nullable=True),
        sa.Column('hash_sha256', sa.String(length=64), nullable=True),
        sa.Column('nombre_original', sa.String(length=255), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('tamanio_bytes', sa.Integer(), nullable=True),
        sa.Column('estado_flujo', sa.String(length=30), nullable=False),
        sa.Column('creado_por', sa.Uuid(), nullable=True),
        sa.Column('revisado_por', sa.Uuid(), nullable=True),
        sa.Column('motivo_devolucion', sa.String(length=255), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['documento_id'], ['documentos.id'], ),
        sa.ForeignKeyConstraint(['creado_por'], ['usuarios.id'], ),
        sa.ForeignKeyConstraint(['revisado_por'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_documentos_versiones_documento_id'), 'documentos_versiones', ['documento_id'], unique=False,
    )
    # ### end commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_documentos_versiones_documento_id'), table_name='documentos_versiones')
    op.drop_table('documentos_versiones')

    op.drop_index(op.f('ix_documentos_menor_id_categoria'), table_name='documentos')
    op.drop_constraint('ck_documentos_estado_flujo', 'documentos', type_='check')
    op.drop_constraint('ck_documentos_categoria', 'documentos', type_='check')
    op.drop_constraint(op.f('fk_documentos_revisado_por_usuarios'), 'documentos', type_='foreignkey')
    op.drop_column('documentos', 'motivo_devolucion')
    op.drop_column('documentos', 'revisado_en')
    op.drop_column('documentos', 'revisado_por')
    op.drop_column('documentos', 'tamanio_bytes')
    op.drop_column('documentos', 'mime_type')
    op.drop_column('documentos', 'nombre_original')
    # ### end Alembic commands ###
