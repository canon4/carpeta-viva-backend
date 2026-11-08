"""Asistente de IA: Repositorios (persistencia).

Busca, resume y clasifica con citas; consulta solo por la capa de aplicación.

`FragmentoDocumentoRepository.reemplazar_fragmentos` es el upsert idempotente que exige la
corrección de seguridad de ADR-0010 sección 1.3/1.4: si la tarea de indexación en segundo plano
se reintenta, primero borra los fragmentos previos de esa misma versión del documento/reporte y
luego inserta los nuevos, nunca duplica.
"""
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import FragmentoDocumento, IaConsulta


class FragmentoDocumentoRepository:
    def __init__(self, session: Session):
        self.session = session

    def reemplazar_fragmentos(
        self,
        *,
        documento_id: uuid.UUID | None,
        reporte_id: uuid.UUID | None,
        version_documento: int,
        menor_id: uuid.UUID | None,
        hogar_id: uuid.UUID | None,
        seccion: str | None,
        modelo_embedding: str,
        fragmentos: list[tuple[int, str, list[float]]],
    ) -> list[FragmentoDocumento]:
        """Upsert idempotente (reintentar no duplica): borra los fragmentos existentes de esa
        misma versión del documento/reporte y escribe los nuevos en una sola transacción."""
        if (documento_id is None) == (reporte_id is None):
            raise ValueError("Debe indicarse exactamente uno de documento_id o reporte_id")

        condicion = (
            FragmentoDocumento.documento_id == documento_id
            if documento_id is not None
            else FragmentoDocumento.reporte_id == reporte_id
        )
        self.session.execute(
            delete(FragmentoDocumento).where(condicion, FragmentoDocumento.version_documento == version_documento)
        )

        creados = []
        for orden, texto, embedding in fragmentos:
            fragmento = FragmentoDocumento(
                documento_id=documento_id,
                reporte_id=reporte_id,
                menor_id=menor_id,
                hogar_id=hogar_id,
                seccion=seccion,
                version_documento=version_documento,
                orden=orden,
                texto=texto,
                embedding=embedding,
                modelo_embedding=modelo_embedding,
            )
            self.session.add(fragmento)
            creados.append(fragmento)
        self.session.commit()
        return creados

    def por_menores_y_hogares(
        self, menor_ids: list[uuid.UUID], hogar_ids: list[uuid.UUID]
    ) -> list[FragmentoDocumento]:
        """Primer filtro, de grano grueso, por el ámbito ya resuelto como permitido (ADR-0010,
        sección 1.5 paso 4): nunca se consulta esta tabla sin que `ia.application` haya resuelto
        antes qué `menor_id`/`hogar_id` puede ver el usuario. La revalidación fila por fila
        (sección, versión vigente, permiso real) ocurre después, en la capa de aplicación."""
        resultado: list[FragmentoDocumento] = []
        if menor_ids:
            consulta = select(FragmentoDocumento).where(FragmentoDocumento.menor_id.in_(menor_ids))
            resultado += list(self.session.scalars(consulta))
        if hogar_ids:
            consulta_hogar = select(FragmentoDocumento).where(FragmentoDocumento.hogar_id.in_(hogar_ids))
            resultado += list(self.session.scalars(consulta_hogar))
        return resultado

    def tiene_fragmentos(self, *, documento_id: uuid.UUID | None, reporte_id: uuid.UUID | None, version: int) -> bool:
        condicion = (
            FragmentoDocumento.documento_id == documento_id
            if documento_id is not None
            else FragmentoDocumento.reporte_id == reporte_id
        )
        consulta = select(FragmentoDocumento.id).where(condicion, FragmentoDocumento.version_documento == version).limit(1)
        return self.session.scalars(consulta).first() is not None


class IaConsultaRepository:
    def __init__(self, session: Session):
        self.session = session

    def crear(self, consulta: IaConsulta) -> IaConsulta:
        self.session.add(consulta)
        self.session.commit()
        return consulta

    def por_id(self, consulta_id: uuid.UUID) -> IaConsulta | None:
        return self.session.get(IaConsulta, consulta_id)

    def listar_por_usuario(self, usuario_id: uuid.UUID) -> list[IaConsulta]:
        consulta = select(IaConsulta).where(IaConsulta.usuario_id == usuario_id).order_by(IaConsulta.creado_en.desc())
        return list(self.session.scalars(consulta))

    def listar_todas(self) -> list[IaConsulta]:
        consulta = select(IaConsulta).order_by(IaConsulta.creado_en.desc())
        return list(self.session.scalars(consulta))
