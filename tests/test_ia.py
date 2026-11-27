"""Pruebas del Asistente de IA (ADR-0010, sección 1).

Cubre, en línea con la revisión de seguridad de la ADR:
- Autorización por fila en el flujo RAG: un profesional no asignado a un menor no puede
  recuperar sus fragmentos aunque adivine el `menor_id` en la pregunta.
- Sin fragmentos permitidos/recuperados, nunca se llama al proveedor de LLM externo.
- `auditor` nunca recibe `pregunta`/`respuesta` en texto completo, solo metadatos.
- La lectura del propio historial revalida el acceso vigente (no solo "es mío"): si el acceso
  ya fue revocado (aquí, por egreso del menor, RF7), el contenido queda redactado.

Nunca se usa una clave real de Anthropic ni se hace una llamada de red real: donde se necesita
un proveedor de LLM, se inyecta `ProveedorLLMFalso` (implementa `ProveedorLLM`).
"""
import uuid

from app.core.ia_llm import ProveedorLLM, RespuestaLLM
from app.modules.auth.models import Usuario
from app.modules.ia.application import consultar
from app.modules.ia.schemas import MENSAJE_PIDE_IDENTIFICACION, ConsultaCreate

from ._helpers import (
    asignar_profesional_a_menor,
    auth_header,
    crear_madre,
    crear_profesional,
    crear_usuario,
    crear_zona_y_hogar,
    login,
    vincular_hogar_madre,
)


class ProveedorLLMFalso(ProveedorLLM):
    """Nunca hace red: para pruebas, cuenta cuántas veces se le pidió generar una respuesta."""

    nombre = "falso"

    def __init__(self):
        self.llamadas = 0

    def generar(self, prompt: str, *, contexto: str, instrucciones_sistema: str) -> RespuestaLLM:
        self.llamadas += 1
        return RespuestaLLM(texto=f"Resumen de prueba basado en: {contexto[:80]}", modelo="falso-1", proveedor=self.nombre)


def crear_menor(client, h, nombres="Menor IA"):
    r = client.post(
        "/api/v1/menores",
        json={"nombres": nombres, "apellidos": "Sintético", "fecha_nacimiento": "2017-01-01"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def ingresar_menor(client, h_admin, menor_id, hogar_id):
    r = client.post(
        "/api/v1/asignaciones",
        json={"menor_id": menor_id, "hogar_id": hogar_id, "fecha_inicio": "2026-01-01", "tipo_movimiento": "ingreso"},
        headers=h_admin,
    )
    assert r.status_code == 201, r.text
    return r.json()


def subir_documento_texto(client, h, menor_id, texto, categoria="otros", titulo="Documento de prueba"):
    return client.post(
        "/api/v1/documentos",
        data={"menor_id": menor_id, "categoria": categoria, "titulo": titulo},
        files={"archivo": ("doc.txt", texto.encode("utf-8"), "text/plain")},
        headers=h,
    )


def _usuario_por_email(session_factory, email) -> Usuario:
    with session_factory() as session:
        usuario = session.query(Usuario).filter_by(email=email).one()
        session.expunge(usuario)
        return usuario


# ---------------------------------------------------------------------------
# Autorización por fila en el flujo RAG
# ---------------------------------------------------------------------------

def test_profesional_no_asignado_no_recupera_fragmentos_de_menor_ajeno(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_ia1@prueba.local", "admin")

    menor_a = crear_menor(client, h_admin, "Menor A")
    menor_b = crear_menor(client, h_admin, "Menor B")
    ingresar_menor(client, h_admin, menor_a, hogar_id)
    ingresar_menor(client, h_admin, menor_b, hogar_id)

    uid_prof_a = crear_usuario(session_factory, "prof_ia1a@prueba.local", "profesional")
    prof_a_id = crear_profesional(session_factory, uid_prof_a, "trabajo_social")
    asignar_profesional_a_menor(session_factory, menor_a, prof_a_id, "trabajo_social")

    uid_prof_b = crear_usuario(session_factory, "prof_ia1b@prueba.local", "profesional")
    prof_b_id = crear_profesional(session_factory, uid_prof_b, "trabajo_social")
    asignar_profesional_a_menor(session_factory, menor_b, prof_b_id, "trabajo_social")

    marca_secreta = "CLAVE-SECRETA-MENOR-B-99887"
    h_prof_b = {"Authorization": f"Bearer {login(client, 'prof_ia1b@prueba.local')}"}
    r = subir_documento_texto(client, h_prof_b, menor_b, f"Informe confidencial del menor B. {marca_secreta}.")
    assert r.status_code == 201, r.text

    h_prof_a = {"Authorization": f"Bearer {login(client, 'prof_ia1a@prueba.local')}"}

    # El profesional A adivina el menor_id del menor B (ajeno) en la propia pregunta: debe
    # comportarse exactamente igual que "sin fuente", sin filtrar el contenido ni revelar que
    # el documento existe.
    r = client.post(
        "/api/v1/ia/consultas",
        json={"pregunta": marca_secreta, "menor_id": menor_b},
        headers=h_prof_a,
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["sin_resultado"] is True
    assert marca_secreta not in cuerpo["respuesta"]
    assert cuerpo["fragmentos_usados"] == []

    # Tampoco aparece si pregunta sin indicar menor_id: el ámbito permitido de A nunca incluye
    # fragmentos de B, así que la búsqueda por similitud ni siquiera los considera.
    r = client.post("/api/v1/ia/consultas", json={"pregunta": marca_secreta}, headers=h_prof_a)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["sin_resultado"] is True
    assert marca_secreta not in cuerpo["respuesta"]

    # Revalidación directa de la capa de aplicación (defensa en profundidad, ADR-0010 sección
    # 1.5 paso 5): aunque se construya el candidato con el menor_id ajeno, la lista de
    # fragmentos autorizados para A siempre llega vacía para el menor B.
    from app.modules.ia.application import _candidatos_permitidos

    usuario_a = _usuario_por_email(session_factory, "prof_ia1a@prueba.local")
    with session_factory() as session:
        permitidos = _candidatos_permitidos(session, usuario_a, uuid.UUID(menor_b), None)
        assert permitidos == []


# ---------------------------------------------------------------------------
# Sin fragmentos, nunca se llama al proveedor de LLM externo
# ---------------------------------------------------------------------------

def test_sin_fragmentos_no_llama_al_proveedor_llm_pero_si_llama_cuando_hay_fuente(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_ia2@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin, "Menor IA2")
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_prof = crear_usuario(session_factory, "prof_ia2@prueba.local", "profesional")
    prof_id = crear_profesional(session_factory, uid_prof, "trabajo_social")
    asignar_profesional_a_menor(session_factory, menor_id, prof_id, "trabajo_social")

    usuario_prof = _usuario_por_email(session_factory, "prof_ia2@prueba.local")

    # Sin ningún documento subido/indexado todavía: no hay fragmentos permitidos -> jamás se
    # invoca el proveedor de LLM (ADR-0002 punto 2 / CLAUDE.md: "sin fuente recuperada, responde
    # que no encontró información").
    fake = ProveedorLLMFalso()
    with session_factory() as session:
        consulta = consultar(
            session,
            usuario_prof,
            ConsultaCreate(pregunta="¿Qué dice el expediente?", menor_id=uuid.UUID(menor_id)),
            proveedor_llm=fake,
        )
        assert consulta.sin_resultado is True
        assert consulta.respuesta  # mensaje fijo de "no encontré información"
    assert fake.llamadas == 0

    # Se sube (y se indexa automáticamente en segundo plano) un documento real.
    h_prof = {"Authorization": f"Bearer {login(client, 'prof_ia2@prueba.local')}"}
    r = subir_documento_texto(
        client, h_prof, menor_id, "El menor presenta buen desarrollo escolar y asiste a controles médicos."
    )
    assert r.status_code == 201, r.text

    fake2 = ProveedorLLMFalso()
    with session_factory() as session:
        consulta = consultar(
            session,
            usuario_prof,
            ConsultaCreate(pregunta="¿Cómo va el desarrollo escolar del menor?", menor_id=uuid.UUID(menor_id)),
            proveedor_llm=fake2,
        )
        assert consulta.sin_resultado is False
        assert len(consulta.fragmentos_usados) >= 1
    assert fake2.llamadas == 1


# ---------------------------------------------------------------------------
# Sin menor ni hogar elegido, se pide identificar al menor antes de buscar
# ---------------------------------------------------------------------------

def test_sin_menor_ni_hogar_pide_identificacion_y_no_llama_al_proveedor_llm(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_ia4@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin, "Camila")
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_prof = crear_usuario(session_factory, "prof_ia4@prueba.local", "profesional")
    prof_id = crear_profesional(session_factory, uid_prof, "trabajo_social")
    asignar_profesional_a_menor(session_factory, menor_id, prof_id, "trabajo_social")
    h_prof = {"Authorization": f"Bearer {login(client, 'prof_ia4@prueba.local')}"}

    r = subir_documento_texto(client, h_prof, menor_id, "La menor asiste a controles médicos regulares.")
    assert r.status_code == 201, r.text

    usuario_prof = _usuario_por_email(session_factory, "prof_ia4@prueba.local")

    # Sin menor_id ni hogar_id, y sin ningún nombre reconocible en la pregunta: aunque haya
    # fragmentos permitidos para este profesional, no se busca entre todos a la vez (mezclaría
    # datos de varios NNA) — se pide identificar al menor, sin llamar al proveedor de LLM.
    fake = ProveedorLLMFalso()
    with session_factory() as session:
        consulta = consultar(
            session, usuario_prof, ConsultaCreate(pregunta="¿Qué documentos faltan por revisar?"), proveedor_llm=fake
        )
        assert consulta.sin_resultado is True
        assert consulta.respuesta == MENSAJE_PIDE_IDENTIFICACION
        assert consulta.fragmentos_usados == []
    assert fake.llamadas == 0

    # Con el menor identificado por el selector, la consulta sí busca y responde con fuente.
    fake2 = ProveedorLLMFalso()
    with session_factory() as session:
        consulta = consultar(
            session,
            usuario_prof,
            ConsultaCreate(pregunta="¿Cómo va el desarrollo del menor?", menor_id=uuid.UUID(menor_id)),
            proveedor_llm=fake2,
        )
        assert consulta.sin_resultado is False
    assert fake2.llamadas == 1


# ---------------------------------------------------------------------------
# El nombre del menor en la propia pregunta identifica automáticamente (sin
# selector), y si hay más de uno que coincide se pide desambiguar
# ---------------------------------------------------------------------------

def test_nombre_en_la_pregunta_identifica_automaticamente_al_menor(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_ia5@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin, "Carlitos")
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_madre = crear_usuario(session_factory, "madre_ia5@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900111222")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)
    h_madre = {"Authorization": f"Bearer {login(client, 'madre_ia5@prueba.local')}"}

    r = subir_documento_texto(client, h_madre, menor_id, "Asiste al colegio todos los días sin faltas.")
    assert r.status_code == 201, r.text

    usuario_madre = _usuario_por_email(session_factory, "madre_ia5@prueba.local")

    # Sin elegir nada en el selector, pero nombrando al menor de su propio hogar: se identifica
    # solo y responde con fuente (no pide identificación).
    fake = ProveedorLLMFalso()
    with session_factory() as session:
        consulta = consultar(
            session, usuario_madre, ConsultaCreate(pregunta="¿Cómo va Carlitos en el colegio?"), proveedor_llm=fake
        )
        assert consulta.sin_resultado is False
        assert consulta.menor_id == uuid.UUID(menor_id)
        assert "Carlitos" in consulta.respuesta  # aviso de identificación automática
    assert fake.llamadas == 1

    # Un segundo menor con el mismo primer nombre en el mismo hogar: ahora es ambiguo, se pide
    # desambiguar en vez de adivinar, sin llamar al proveedor de LLM.
    menor_id_2 = crear_menor(client, h_admin, "Carlitos")
    ingresar_menor(client, h_admin, menor_id_2, hogar_id)

    fake2 = ProveedorLLMFalso()
    with session_factory() as session:
        consulta = consultar(
            session, usuario_madre, ConsultaCreate(pregunta="¿Cómo va Carlitos en el colegio?"), proveedor_llm=fake2
        )
        assert consulta.sin_resultado is True
        assert consulta.menor_id is None
        assert "más de un menor" in consulta.respuesta
    assert fake2.llamadas == 0


# ---------------------------------------------------------------------------
# `auditor` nunca ve pregunta/respuesta en texto completo
# ---------------------------------------------------------------------------

def test_auditor_nunca_ve_pregunta_ni_respuesta(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_ia3@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin, "Menor IA3")
    ingresar_menor(client, h_admin, menor_id, hogar_id)

    uid_prof = crear_usuario(session_factory, "prof_ia3@prueba.local", "profesional")
    prof_id = crear_profesional(session_factory, uid_prof, "trabajo_social")
    asignar_profesional_a_menor(session_factory, menor_id, prof_id, "trabajo_social")
    h_prof = {"Authorization": f"Bearer {login(client, 'prof_ia3@prueba.local')}"}

    pregunta_sensible = "¿Cuál es el diagnóstico confidencial del menor?"
    r = client.post(
        "/api/v1/ia/consultas", json={"pregunta": pregunta_sensible, "menor_id": menor_id}, headers=h_prof
    )
    assert r.status_code == 200
    consulta_id = r.json()["id"]

    h_auditor = auth_header(client, session_factory, "auditor_ia3@prueba.local", "auditor")

    r = client.get("/api/v1/ia/consultas", headers=h_auditor)
    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo) >= 1
    for item in cuerpo:
        assert "pregunta" not in item
        assert "respuesta" not in item
        assert "usuario_id" in item  # sí ve metadatos

    r = client.get(f"/api/v1/ia/consultas/{consulta_id}", headers=h_auditor)
    assert r.status_code == 200
    detalle = r.json()
    assert "pregunta" not in detalle
    assert "respuesta" not in detalle
    assert detalle["id"] == consulta_id


# ---------------------------------------------------------------------------
# Revalidación de acceso al leer el propio historial (sección 1.4, hueco corregido)
# ---------------------------------------------------------------------------

def test_revalidacion_historial_redacta_si_acceso_ya_no_vigente(client, session_factory):
    zona_id, hogar_id = crear_zona_y_hogar(session_factory)
    h_admin = auth_header(client, session_factory, "admin_ia4@prueba.local", "admin")
    menor_id = crear_menor(client, h_admin, "Menor IA4")

    uid_madre = crear_usuario(session_factory, "madre_ia4@prueba.local", "madre")
    madre_id = crear_madre(session_factory, uid_madre, "900-ia4")
    vincular_hogar_madre(session_factory, hogar_id, madre_id)

    asignacion = ingresar_menor(client, h_admin, menor_id, hogar_id)
    asignacion_id = asignacion["id"]

    h_madre = {"Authorization": f"Bearer {login(client, 'madre_ia4@prueba.local')}"}

    pregunta = "¿Hay algo pendiente con este expediente?"
    r = client.post("/api/v1/ia/consultas", json={"pregunta": pregunta, "menor_id": menor_id}, headers=h_madre)
    assert r.status_code == 200
    consulta_id = r.json()["id"]
    assert r.json()["pregunta"] == pregunta

    # Mientras el acceso sigue vigente, la propia madre ve su historial sin redactar.
    r = client.get(f"/api/v1/ia/consultas/{consulta_id}", headers=h_madre)
    assert r.json()["pregunta"] == pregunta

    # Egreso del menor (RF7: el expediente se oculta a la madre saliente).
    r = client.put(f"/api/v1/asignaciones/{asignacion_id}/cerrar", json={"motivo": "egreso"}, headers=h_admin)
    assert r.status_code == 200

    r = client.get(f"/api/v1/ia/consultas/{consulta_id}", headers=h_madre)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["pregunta"] != pregunta
    assert "ya no accesible" in cuerpo["pregunta"]
    assert "ya no accesible" in cuerpo["respuesta"]
    # Los metadatos (para transparencia de su propia actividad pasada) siguen presentes.
    assert cuerpo["id"] == consulta_id
    assert cuerpo["modelo"]

    r = client.get("/api/v1/ia/consultas", headers=h_madre)
    assert r.status_code == 200
    assert all(c["pregunta"] != pregunta for c in r.json())
