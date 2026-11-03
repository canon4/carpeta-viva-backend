"""expediente del menor: historial, familiares y permisos por seccion

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-02 00:00:00.000000

Ver docs/adr/0007-expediente-menor-permisos-historial.md para el detalle
tabla por tabla. Esta migracion solo crea/altera esquema; los modelos
SQLAlchemy correspondientes los agrega el agente backend por separado.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- menores: columnas nuevas ---
    op.add_column('menores', sa.Column('tipo_documento', sa.String(length=30), nullable=True))
    op.add_column('menores', sa.Column('numero_documento', sa.String(length=50), nullable=True))
    op.create_index(
        op.f('ix_menores_numero_documento'), 'menores', ['numero_documento'],
        unique=True, postgresql_where=sa.text('numero_documento IS NOT NULL'),
    )
    op.create_check_constraint(
        'ck_menores_tipo_documento',
        'menores',
        "tipo_documento IS NULL OR tipo_documento IN "
        "('registro_civil', 'tarjeta_identidad', 'cedula', 'pasaporte', 'sin_documento')",
    )
    op.create_check_constraint(
        'ck_menores_estado_actual',
        'menores',
        "estado_actual IN ('activo', 'egresado', 'evadido', 'fallecido')",
    )

    # --- menores_history ---
    op.create_table(
        'menores_history',
        sa.Column('menor_id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('nombres', sa.String(length=120), nullable=False),
        sa.Column('apellidos', sa.String(length=120), nullable=False),
        sa.Column('fecha_nacimiento', sa.Date(), nullable=False),
        sa.Column('genero', sa.String(length=20), nullable=True),
        sa.Column('tipo_documento', sa.String(length=30), nullable=True),
        sa.Column('numero_documento', sa.String(length=50), nullable=True),
        sa.Column('estado_actual', sa.String(length=30), nullable=False),
        sa.Column('cambiado_por', sa.Uuid(), nullable=True),
        sa.Column('motivo', sa.String(length=255), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['cambiado_por'], ['usuarios.id'], ),
        sa.ForeignKeyConstraint(['menor_id'], ['menores.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_menores_history_menor_id'), 'menores_history', ['menor_id'], unique=False)

    # --- menores_familiares ---
    op.create_table(
        'menores_familiares',
        sa.Column('menor_id', sa.Uuid(), nullable=False),
        sa.Column('parentesco', sa.String(length=20), nullable=False),
        sa.Column('nombres', sa.String(length=120), nullable=True),
        sa.Column('numero_identificacion', sa.String(length=50), nullable=True),
        sa.Column('telefono', sa.String(length=30), nullable=True),
        sa.Column('direccion', sa.String(length=255), nullable=True),
        sa.Column('estado_vital', sa.String(length=20), nullable=False),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['menor_id'], ['menores.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("parentesco IN ('padre', 'madre', 'otro')", name='ck_menores_familiares_parentesco'),
        sa.CheckConstraint("estado_vital IN ('vivo', 'fallecido', 'desconocido')", name='ck_menores_familiares_estado_vital'),
    )
    op.create_index(op.f('ix_menores_familiares_menor_id'), 'menores_familiares', ['menor_id'], unique=False)

    # --- permisos_expediente ---
    op.create_table(
        'permisos_expediente',
        sa.Column('menor_id', sa.Uuid(), nullable=False),
        sa.Column('seccion', sa.String(length=20), nullable=False),
        sa.Column('usuario_id', sa.Uuid(), nullable=False),
        sa.Column('otorgado_por', sa.Uuid(), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('notas', sa.String(length=255), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['menor_id'], ['menores.id'], ),
        sa.ForeignKeyConstraint(['otorgado_por'], ['usuarios.id'], ),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('menor_id', 'seccion', 'usuario_id', name='uq_permisos_expediente_menor_seccion_usuario'),
        sa.CheckConstraint("seccion IN ('familia', 'salud', 'psicosocial')", name='ck_permisos_expediente_seccion'),
    )
    op.create_index(op.f('ix_permisos_expediente_menor_id'), 'permisos_expediente', ['menor_id'], unique=False)
    op.create_index(op.f('ix_permisos_expediente_usuario_id'), 'permisos_expediente', ['usuario_id'], unique=False)

    # --- asignaciones: columnas nuevas ---
    op.add_column('asignaciones', sa.Column('version', sa.Integer(), server_default='1', nullable=False))
    op.add_column(
        'asignaciones',
        sa.Column('tipo_movimiento', sa.String(length=20), server_default='ingreso', nullable=False),
    )
    op.add_column('asignaciones', sa.Column('acta_referencia', sa.String(length=255), nullable=True))
    op.add_column('asignaciones', sa.Column('motivo', sa.String(length=255), nullable=True))
    op.add_column('asignaciones', sa.Column('registrado_por', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('fk_asignaciones_registrado_por_usuarios'), 'asignaciones', 'usuarios',
        ['registrado_por'], ['id'],
    )
    op.create_check_constraint(
        'ck_asignaciones_tipo_movimiento',
        'asignaciones',
        "tipo_movimiento IN ('ingreso', 'traslado', 'egreso')",
    )

    # --- asignaciones_history ---
    op.create_table(
        'asignaciones_history',
        sa.Column('asignacion_id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('menor_id', sa.Uuid(), nullable=False),
        sa.Column('hogar_id', sa.Uuid(), nullable=False),
        sa.Column('fecha_inicio', sa.Date(), nullable=False),
        sa.Column('fecha_fin', sa.Date(), nullable=True),
        sa.Column('estado', sa.String(length=30), nullable=False),
        sa.Column('tipo_movimiento', sa.String(length=20), nullable=False),
        sa.Column('acta_referencia', sa.String(length=255), nullable=True),
        sa.Column('motivo', sa.String(length=255), nullable=True),
        sa.Column('cambiado_por', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['asignacion_id'], ['asignaciones.id'], ),
        sa.ForeignKeyConstraint(['cambiado_por'], ['usuarios.id'], ),
        sa.ForeignKeyConstraint(['hogar_id'], ['hogares_sustitutos.id'], ),
        sa.ForeignKeyConstraint(['menor_id'], ['menores.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_asignaciones_history_asignacion_id'), 'asignaciones_history', ['asignacion_id'], unique=False)
    op.create_index(op.f('ix_asignaciones_history_menor_id'), 'asignaciones_history', ['menor_id'], unique=False)
    # ### end commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_asignaciones_history_menor_id'), table_name='asignaciones_history')
    op.drop_index(op.f('ix_asignaciones_history_asignacion_id'), table_name='asignaciones_history')
    op.drop_table('asignaciones_history')

    op.drop_constraint('ck_asignaciones_tipo_movimiento', 'asignaciones', type_='check')
    op.drop_constraint(op.f('fk_asignaciones_registrado_por_usuarios'), 'asignaciones', type_='foreignkey')
    op.drop_column('asignaciones', 'registrado_por')
    op.drop_column('asignaciones', 'motivo')
    op.drop_column('asignaciones', 'acta_referencia')
    op.drop_column('asignaciones', 'tipo_movimiento')
    op.drop_column('asignaciones', 'version')

    op.drop_index(op.f('ix_permisos_expediente_usuario_id'), table_name='permisos_expediente')
    op.drop_index(op.f('ix_permisos_expediente_menor_id'), table_name='permisos_expediente')
    op.drop_table('permisos_expediente')

    op.drop_index(op.f('ix_menores_familiares_menor_id'), table_name='menores_familiares')
    op.drop_table('menores_familiares')

    op.drop_index(op.f('ix_menores_history_menor_id'), table_name='menores_history')
    op.drop_table('menores_history')

    op.drop_constraint('ck_menores_estado_actual', 'menores', type_='check')
    op.drop_constraint('ck_menores_tipo_documento', 'menores', type_='check')
    op.drop_index(op.f('ix_menores_numero_documento'), table_name='menores')
    op.drop_column('menores', 'numero_documento')
    op.drop_column('menores', 'tipo_documento')
    # ### end Alembic commands ###
