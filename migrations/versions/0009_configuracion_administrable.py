"""configuracion: módulo transversal administrable (catálogos y parámetros)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-14 00:00:00.000000

ADR-0013: generaliza el patrón de "configuración editable por admin sin redespliegue" que
ADR-0009 introdujo solo para `configuracion_alertas`. Crea `catalogos_opciones` (categorías
documentales de menor y de hogar, con `seccion_acceso` desde la primera migración de este
catálogo — sección 5.1, revisión de seguridad) y `configuracion_sistema` (parámetros clave/valor).

Migra el valor actual de `configuracion_alertas.telefono_policia_infancia` (si existe y no es
NULL) a `configuracion_sistema` y elimina `configuracion_alertas` (ADR-0013, sección 7, punto 2).

También retira el `CheckConstraint` `ck_documentos_categoria`: el conjunto de categorías válidas
ya no es fijo en código, `admin` puede agregar categorías nuevas en `catalogos_opciones` sin
redespliegue; la validación pasa a la capa de aplicación (`documentos.application.crear_documento`
contra `configuracion.application.valor_valido_en_catalogo`).
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Semilla de categorías documentales (ADR-0013, sección 7.1): valores/etiquetas actuales de
# `CATEGORIAS_MENOR`/`CATEGORIAS_HOGAR` (app/modules/documentos/domain.py), con `seccion_acceso`
# fijado según `SECCION_POR_CATEGORIA` de ese mismo archivo, para no perder la clasificación de
# hoy al migrar.
_SEED_MENOR = [
    ("identidad", "Identidad", 0, None),
    ("salud", "Salud", 1, "salud"),
    ("psicosocial", "Psicosocial", 2, "psicosocial"),
    ("educacion", "Educación", 3, None),
    ("familia_red_apoyo", "Familia y red de apoyo", 4, "familia"),
    ("actas_traslados", "Actas de traslado", 5, None),
    ("otros", "Otros", 6, None),
]
_SEED_HOGAR = [
    ("madre_habilitacion", "Habilitación de la madre", 0, None),
    ("otros", "Otros", 1, None),
]


def upgrade() -> None:
    op.create_table(
        "catalogos_opciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("grupo", sa.String(length=60), nullable=False),
        sa.Column("valor", sa.String(length=100), nullable=False),
        sa.Column("etiqueta", sa.String(length=200), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("seccion_acceso", sa.String(length=20), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actualizado_por", sa.Uuid(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.UniqueConstraint("grupo", "valor", name="uq_catalogos_opciones_grupo_valor"),
    )
    op.create_index("ix_catalogos_opciones_grupo", "catalogos_opciones", ["grupo"])

    op.create_table(
        "configuracion_sistema",
        sa.Column("clave", sa.String(length=100), primary_key=True),
        sa.Column("valor", sa.Text(), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actualizado_por", sa.Uuid(), sa.ForeignKey("usuarios.id"), nullable=True),
    )

    catalogos_opciones = sa.table(
        "catalogos_opciones",
        sa.column("id", sa.Uuid()),
        sa.column("grupo", sa.String()),
        sa.column("valor", sa.String()),
        sa.column("etiqueta", sa.String()),
        sa.column("orden", sa.Integer()),
        sa.column("seccion_acceso", sa.String()),
    )
    filas = []
    for valor, etiqueta, orden, seccion_acceso in _SEED_MENOR:
        filas.append(
            {
                "id": uuid.uuid4(),
                "grupo": "categoria_documento_menor",
                "valor": valor,
                "etiqueta": etiqueta,
                "orden": orden,
                "seccion_acceso": seccion_acceso,
            }
        )
    for valor, etiqueta, orden, seccion_acceso in _SEED_HOGAR:
        filas.append(
            {
                "id": uuid.uuid4(),
                "grupo": "categoria_documento_hogar",
                "valor": valor,
                "etiqueta": etiqueta,
                "orden": orden,
                "seccion_acceso": seccion_acceso,
            }
        )
    op.bulk_insert(catalogos_opciones, filas)

    # Migra el teléfono de la Policía de Infancia y Adolescencia desde `configuracion_alertas`
    # (ADR-0009) si la fila existe y tiene un valor no NULL.
    conexion = op.get_bind()
    inspector = sa.inspect(conexion)
    if "configuracion_alertas" in inspector.get_table_names():
        fila = conexion.execute(
            sa.text("SELECT telefono_policia_infancia FROM configuracion_alertas WHERE id = 1")
        ).first()
        if fila is not None and fila[0]:
            conexion.execute(
                sa.text(
                    "INSERT INTO configuracion_sistema (clave, valor) VALUES (:clave, :valor)"
                ),
                {"clave": "telefono_policia_infancia", "valor": fila[0]},
            )
        op.drop_table("configuracion_alertas")

    # El conjunto de categorías válidas ya no es fijo en código (ADR-0013); retira el
    # CheckConstraint que lo fijaba a nivel de base de datos.
    op.drop_constraint("ck_documentos_categoria", "documentos", type_="check")


def downgrade() -> None:
    op.create_check_constraint(
        "ck_documentos_categoria",
        "documentos",
        "categoria IN ('identidad', 'salud', 'psicosocial', 'educacion', "
        "'familia_red_apoyo', 'actas_traslados', 'madre_habilitacion', 'otros')",
    )

    op.create_table(
        "configuracion_alertas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telefono_policia_infancia", sa.String(length=60), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actualizado_por", sa.Uuid(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_configuracion_alertas_fila_unica"),
    )
    conexion = op.get_bind()
    fila = conexion.execute(
        sa.text("SELECT valor FROM configuracion_sistema WHERE clave = 'telefono_policia_infancia'")
    ).first()
    telefono = fila[0] if fila is not None else None
    conexion.execute(
        sa.text("INSERT INTO configuracion_alertas (id, telefono_policia_infancia) VALUES (1, :telefono)"),
        {"telefono": telefono},
    )

    op.drop_table("configuracion_sistema")
    op.drop_index("ix_catalogos_opciones_grupo", table_name="catalogos_opciones")
    op.drop_table("catalogos_opciones")
