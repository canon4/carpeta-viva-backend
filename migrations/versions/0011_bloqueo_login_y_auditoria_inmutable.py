"""bloqueo por intentos fallidos, revocación de tokens y auditoría inmutable

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-17 00:00:00.000000

ADR-0016 (correcciones de seguridad de la revisión del 17-11-2026):
- `usuarios.intentos_fallidos` y `usuarios.bloqueado_hasta`: bloqueo temporal tras N intentos
  fallidos de inicio de sesión (RF0.5).
- `usuarios.credenciales_cambiadas_en`: los JWT emitidos antes de esa fecha dejan de valer
  (cambio de contraseña, RF0.4).
- En PostgreSQL, un trigger impide UPDATE y DELETE sobre `auditoria_accesos`: la auditoría deja de
  ser de solo inserción "por convención" (RF11, RNF11). En SQLite (pruebas) no se crea.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usuarios", sa.Column("intentos_fallidos", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("usuarios", sa.Column("bloqueado_hasta", sa.DateTime(timezone=True), nullable=True))
    op.add_column("usuarios", sa.Column("credenciales_cambiadas_en", sa.DateTime(timezone=True), nullable=True))

    if op.get_context().dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION auditoria_solo_insercion() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'auditoria_accesos es de solo inserción';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER auditoria_accesos_inmutable
            BEFORE UPDATE OR DELETE ON auditoria_accesos
            FOR EACH ROW EXECUTE FUNCTION auditoria_solo_insercion();
            """
        )
        op.execute(
            """
            CREATE TRIGGER auditoria_accesos_sin_truncate
            BEFORE TRUNCATE ON auditoria_accesos
            FOR EACH STATEMENT EXECUTE FUNCTION auditoria_solo_insercion();
            """
        )


def downgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS auditoria_accesos_sin_truncate ON auditoria_accesos")
        op.execute("DROP TRIGGER IF EXISTS auditoria_accesos_inmutable ON auditoria_accesos")
        op.execute("DROP FUNCTION IF EXISTS auditoria_solo_insercion()")
    op.drop_column("usuarios", "credenciales_cambiadas_en")
    op.drop_column("usuarios", "bloqueado_hasta")
    op.drop_column("usuarios", "intentos_fallidos")
