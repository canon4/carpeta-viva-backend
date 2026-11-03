"""Gestión Documental: Repositorios (persistencia).

Carga, clasificación, versionado y flujo de revisión: la madre crea, el profesional aprueba.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Documento, DocumentoVersion, Reporte


class DocumentoRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, documento: Documento) -> Documento:
        self.session.add(documento)
        self.session.commit()
        return documento

    def por_id(self, documento_id: uuid.UUID) -> Documento | None:
        return self.session.get(Documento, documento_id)

    def listar(
        self,
        menor_id: uuid.UUID | None = None,
        hogar_id: uuid.UUID | None = None,
        categoria: str | None = None,
        estado_flujo: str | None = None,
    ) -> list[Documento]:
        consulta = select(Documento)
        if menor_id is not None:
            consulta = consulta.where(Documento.menor_id == menor_id)
        if hogar_id is not None:
            consulta = consulta.where(Documento.hogar_id == hogar_id)
        if categoria is not None:
            consulta = consulta.where(Documento.categoria == categoria)
        if estado_flujo is not None:
            consulta = consulta.where(Documento.estado_flujo == estado_flujo)
        return list(self.session.scalars(consulta.order_by(Documento.created_at)))

    def guardar(self, documento: Documento) -> Documento:
        self.session.commit()
        return documento


class DocumentoVersionRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, version: DocumentoVersion) -> DocumentoVersion:
        self.session.add(version)
        self.session.commit()
        return version

    def listar_por_documento(self, documento_id: uuid.UUID) -> list[DocumentoVersion]:
        consulta = (
            select(DocumentoVersion)
            .where(DocumentoVersion.documento_id == documento_id)
            .order_by(DocumentoVersion.version.desc())
        )
        return list(self.session.scalars(consulta))

    def por_documento_y_version(self, documento_id: uuid.UUID, version: int) -> DocumentoVersion | None:
        consulta = select(DocumentoVersion).where(
            DocumentoVersion.documento_id == documento_id, DocumentoVersion.version == version
        )
        return self.session.scalars(consulta).first()


class ReporteRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, reporte: Reporte) -> Reporte:
        self.session.add(reporte)
        self.session.commit()
        return reporte

    def por_id(self, reporte_id: uuid.UUID) -> Reporte | None:
        return self.session.get(Reporte, reporte_id)

    def listar(self, menor_id: uuid.UUID | None = None, tipo_reporte: str | None = None) -> list[Reporte]:
        consulta = select(Reporte)
        if menor_id is not None:
            consulta = consulta.where(Reporte.menor_id == menor_id)
        if tipo_reporte is not None:
            consulta = consulta.where(Reporte.tipo_reporte == tipo_reporte)
        return list(self.session.scalars(consulta.order_by(Reporte.created_at)))
