"""Importa todos los modelos para que Alembic y create_all vean el esquema completo."""
from app.modules.asignaciones.models import Asignacion  # noqa: F401
from app.modules.auditoria.models import AuditoriaAcceso  # noqa: F401
from app.modules.auth.models import Usuario  # noqa: F401
from app.modules.documentos.models import Documento, Reporte  # noqa: F401
from app.modules.madres.models import MadreSustituta  # noqa: F401
from app.modules.menores.models import Menor  # noqa: F401
from app.modules.profesionales.models import MenorProfesional, Profesional  # noqa: F401
from app.modules.zonas_hogares.models import HogarSustituto, Zona  # noqa: F401
