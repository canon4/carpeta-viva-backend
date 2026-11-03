"""alertas y evasiones, citas, inventario del hogar, control de alimentos

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-03 00:00:00.000000

Ver docs/adr/0009-alertas-citas-inventario-alimentos.md (incluida la
seccion "Revision de seguridad") para el detalle tabla por tabla. Esta
migracion solo crea/altera esquema; los modelos SQLAlchemy
correspondientes los agregan los agentes backend por separado.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIPOS_ALERTA = ("evasion", "visita_vencida", "documento_faltante")
ORIGENES_ALERTA = ("manual", "automatica")
ESTADOS_ALERTA = ("activa", "cerrada")

TIPOS_CITA = ("medica", "psicosocial", "reunion_familia", "otro")
ESTADOS_CITA = ("pendiente", "cumplida", "no_asistio")

TIPOS_INVENTARIO = ("cama", "mueble", "otro")
ESTADOS_INVENTARIO = ("bueno", "regular", "malo", "retirado")


def upgrade() -> None:
    """Upgrade schema."""
    # --- profesionales: columna nueva ---
    op.add_column('profesionales', sa.Column('telefono', sa.String(length=30), nullable=True))

    # --- alertas ---
    op.create_table(
        'alertas',
        sa.Column('tipo', sa.String(length=30), nullable=False),
        sa.Column('menor_id', sa.Uuid(), nullable=False),
        sa.Column('origen', sa.String(length=20), nullable=False),
        sa.Column('generada_por', sa.Uuid(), nullable=True),
        sa.Column('descripcion', sa.String(length=255), nullable=False),
        sa.Column('detalle', sa.JSON(), nullable=True),
        sa.Column('estado', sa.String(length=20), server_default='activa', nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['menor_id'], ['menores.id'], ),
        sa.ForeignKeyConstraint(['generada_por'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("tipo IN (" + ", ".join(f"'{t}'" for t in TIPOS_ALERTA) + ")", name='ck_alertas_tipo'),
        sa.CheckConstraint("origen IN (" + ", ".join(f"'{o}'" for o in ORIGENES_ALERTA) + ")", name='ck_alertas_origen'),
        sa.CheckConstraint("estado IN (" + ", ".join(f"'{e}'" for e in ESTADOS_ALERTA) + ")", name='ck_alertas_estado'),
    )
    op.create_index(op.f('ix_alertas_menor_id'), 'alertas', ['menor_id'], unique=False)

    # --- alertas_destinatarios ---
    # `notificado_en` queda reservado para el aviso adicional por SMS/push (punto abierto
    # 7/8 de CLAUDE.md): en esta fase ningun endpoint ni proceso lo escribe, siempre NULL.
    # No exponer en el contrato OpenAPI como si fuera una senal real (ADR-0009, revision
    # de seguridad, punto 6).
    op.create_table(
        'alertas_destinatarios',
        sa.Column('alerta_id', sa.Uuid(), nullable=False),
        sa.Column('usuario_id', sa.Uuid(), nullable=False),
        sa.Column('visto_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'notificado_en', sa.DateTime(timezone=True), nullable=True,
            comment="Reservado para aviso adicional SMS/push (no implementado en esta fase; siempre NULL).",
        ),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['alerta_id'], ['alertas.id'], ),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alerta_id', 'usuario_id', name='uq_alertas_destinatarios_alerta_usuario'),
    )
    op.create_index(op.f('ix_alertas_destinatarios_alerta_id'), 'alertas_destinatarios', ['alerta_id'], unique=False)
    op.create_index(op.f('ix_alertas_destinatarios_usuario_id'), 'alertas_destinatarios', ['usuario_id'], unique=False)

    # --- citas ---
    op.create_table(
        'citas',
        sa.Column('menor_id', sa.Uuid(), nullable=False),
        sa.Column('tipo', sa.String(length=30), nullable=False),
        sa.Column('fecha_hora', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lugar', sa.String(length=255), nullable=True),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('estado', sa.String(length=20), server_default='pendiente', nullable=False),
        sa.Column('registrado_por', sa.Uuid(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['menor_id'], ['menores.id'], ),
        sa.ForeignKeyConstraint(['registrado_por'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("tipo IN (" + ", ".join(f"'{t}'" for t in TIPOS_CITA) + ")", name='ck_citas_tipo'),
        sa.CheckConstraint("estado IN (" + ", ".join(f"'{e}'" for e in ESTADOS_CITA) + ")", name='ck_citas_estado'),
    )
    op.create_index(op.f('ix_citas_menor_id'), 'citas', ['menor_id'], unique=False)

    # --- inventario_items ---
    op.create_table(
        'inventario_items',
        sa.Column('hogar_id', sa.Uuid(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('descripcion', sa.String(length=255), nullable=False),
        sa.Column('cantidad', sa.Integer(), server_default='1', nullable=False),
        sa.Column('estado', sa.String(length=20), server_default='bueno', nullable=False),
        sa.Column('registrado_por', sa.Uuid(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['hogar_id'], ['hogares_sustitutos.id'], ),
        sa.ForeignKeyConstraint(['registrado_por'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("tipo IN (" + ", ".join(f"'{t}'" for t in TIPOS_INVENTARIO) + ")", name='ck_inventario_items_tipo'),
        sa.CheckConstraint("estado IN (" + ", ".join(f"'{e}'" for e in ESTADOS_INVENTARIO) + ")", name='ck_inventario_items_estado'),
    )
    op.create_index(op.f('ix_inventario_items_hogar_id'), 'inventario_items', ['hogar_id'], unique=False)

    # --- hogar_convivientes ---
    op.create_table(
        'hogar_convivientes',
        sa.Column('hogar_id', sa.Uuid(), nullable=False),
        sa.Column('nombres', sa.String(length=120), nullable=False),
        sa.Column('relacion_con_madre', sa.String(length=60), nullable=False),
        sa.Column('fecha_desde', sa.Date(), nullable=True),
        sa.Column('observaciones', sa.String(length=255), nullable=True),
        sa.Column('activo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['hogar_id'], ['hogares_sustitutos.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_hogar_convivientes_hogar_id'), 'hogar_convivientes', ['hogar_id'], unique=False)

    # --- hogar_red_apoyo ---
    op.create_table(
        'hogar_red_apoyo',
        sa.Column('hogar_id', sa.Uuid(), nullable=False),
        sa.Column('nombres', sa.String(length=120), nullable=False),
        sa.Column('relacion', sa.String(length=60), nullable=False),
        sa.Column('telefono', sa.String(length=30), nullable=True),
        sa.Column('observaciones', sa.String(length=255), nullable=True),
        sa.Column('activo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['hogar_id'], ['hogares_sustitutos.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_hogar_red_apoyo_hogar_id'), 'hogar_red_apoyo', ['hogar_id'], unique=False)

    # --- alimentos_items ---
    op.create_table(
        'alimentos_items',
        sa.Column('hogar_id', sa.Uuid(), nullable=False),
        sa.Column('descripcion', sa.String(length=255), nullable=False),
        sa.Column('fecha_ingreso', sa.Date(), nullable=False),
        sa.Column('perecedero', sa.Boolean(), nullable=False),
        sa.Column('fecha_vencimiento', sa.Date(), nullable=True),
        sa.Column('cantidad', sa.Float(), nullable=False),
        sa.Column('unidad', sa.String(length=20), nullable=True),
        sa.Column('consumido', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('registrado_por', sa.Uuid(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['hogar_id'], ['hogares_sustitutos.id'], ),
        sa.ForeignKeyConstraint(['registrado_por'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_alimentos_items_hogar_id'), 'alimentos_items', ['hogar_id'], unique=False)
    # ### end commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_alimentos_items_hogar_id'), table_name='alimentos_items')
    op.drop_table('alimentos_items')

    op.drop_index(op.f('ix_hogar_red_apoyo_hogar_id'), table_name='hogar_red_apoyo')
    op.drop_table('hogar_red_apoyo')

    op.drop_index(op.f('ix_hogar_convivientes_hogar_id'), table_name='hogar_convivientes')
    op.drop_table('hogar_convivientes')

    op.drop_index(op.f('ix_inventario_items_hogar_id'), table_name='inventario_items')
    op.drop_table('inventario_items')

    op.drop_index(op.f('ix_citas_menor_id'), table_name='citas')
    op.drop_table('citas')

    op.drop_index(op.f('ix_alertas_destinatarios_usuario_id'), table_name='alertas_destinatarios')
    op.drop_index(op.f('ix_alertas_destinatarios_alerta_id'), table_name='alertas_destinatarios')
    op.drop_table('alertas_destinatarios')

    op.drop_index(op.f('ix_alertas_menor_id'), table_name='alertas')
    op.drop_table('alertas')

    op.drop_column('profesionales', 'telefono')
    # ### end Alembic commands ###
