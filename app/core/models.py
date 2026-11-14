"""Importa todos los modelos para que Alembic y create_all vean el esquema completo."""
from app.modules.alertas.models import Alerta, AlertaDestinatario  # noqa: F401
from app.modules.alimentos.models import AlimentoChecklistItem, AlimentoItem  # noqa: F401
from app.modules.archivo.models import ExpedienteArchivo  # noqa: F401
from app.modules.asignaciones.models import Asignacion, AsignacionHistory  # noqa: F401
from app.modules.auditoria.models import AuditoriaAcceso  # noqa: F401
from app.modules.auth.models import Usuario  # noqa: F401
from app.modules.citas.models import Cita  # noqa: F401
from app.modules.configuracion.models import CatalogoOpcion, ConfiguracionParametro  # noqa: F401
from app.modules.documentos.models import Documento, DocumentoVersion, Reporte  # noqa: F401
from app.modules.ia.models import FragmentoDocumento, IaConsulta  # noqa: F401
from app.modules.inventario.models import (  # noqa: F401
    HogarConviviente,
    HogarRedApoyo,
    InventarioItem,
    InventarioItemFoto,
)
from app.modules.madres.models import MadreSustituta  # noqa: F401
from app.modules.menores.models import Menor, MenorFamiliar, MenorHistory, PermisoExpediente  # noqa: F401
from app.modules.profesionales.models import MenorProfesional, Profesional  # noqa: F401
from app.modules.reportes.models import InformeGenerado  # noqa: F401
from app.modules.zonas_hogares.models import HogarSustituto, Zona  # noqa: F401
