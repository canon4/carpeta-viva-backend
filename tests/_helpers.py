"""Utilidades compartidas por las pruebas de menores y asignaciones.

No es un módulo de la aplicación: solo ayuda a montar escenarios sintéticos en las pruebas.
Los ids se devuelven como `str` (listos para enviarse en JSON) y se convierten a `uuid.UUID`
solo al usarse como valor de un FK en el ORM.
"""
import uuid

from app.core.security import hash_password
from app.modules.auth.models import Usuario
from app.modules.madres.models import MadreSustituta
from app.modules.profesionales.models import MenorProfesional, Profesional
from app.modules.zonas_hogares.models import HogarSustituto, Zona

CLAVE_SINTETICA = "clave-sintetica-123"


def crear_usuario(session_factory, email, rol, zona_id=None):
    with session_factory() as s:
        usuario = Usuario(
            email=email,
            password_hash=hash_password(CLAVE_SINTETICA),
            rol=rol,
            zona_id=uuid.UUID(zona_id) if zona_id else None,
        )
        s.add(usuario)
        s.commit()
        return str(usuario.id)


def login(client, email, password=CLAVE_SINTETICA):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


def auth_header(client, session_factory, email, rol, zona_id=None):
    crear_usuario(session_factory, email, rol, zona_id)
    token = login(client, email)
    return {"Authorization": f"Bearer {token}"}


def crear_zona_y_hogar(session_factory, nombre_zona="Zona sintética", madre_id=None):
    with session_factory() as s:
        zona = Zona(nombre=nombre_zona)
        s.add(zona)
        s.commit()
        hogar = HogarSustituto(
            zona_id=zona.id, madre_id=uuid.UUID(madre_id) if madre_id else None, capacidad_maxima=6
        )
        s.add(hogar)
        s.commit()
        return str(zona.id), str(hogar.id)


def crear_madre(session_factory, usuario_id, numero_identificacion):
    with session_factory() as s:
        madre = MadreSustituta(
            usuario_id=uuid.UUID(usuario_id) if usuario_id else None,
            nombres="Ana sintética",
            apellidos="Pérez sintética",
            numero_identificacion=numero_identificacion,
        )
        s.add(madre)
        s.commit()
        return str(madre.id)


def vincular_hogar_madre(session_factory, hogar_id, madre_id):
    with session_factory() as s:
        hogar = s.get(HogarSustituto, uuid.UUID(hogar_id))
        hogar.madre_id = uuid.UUID(madre_id)
        s.commit()


def crear_profesional(session_factory, usuario_id, cargo, nombres="Profesional sintético"):
    with session_factory() as s:
        profesional = Profesional(
            usuario_id=uuid.UUID(usuario_id) if usuario_id else None,
            nombres=nombres,
            apellidos="Prueba",
            cargo=cargo,
        )
        s.add(profesional)
        s.commit()
        return str(profesional.id)


def asignar_profesional_a_menor(session_factory, menor_id, profesional_id, rol_asignado):
    with session_factory() as s:
        s.add(
            MenorProfesional(
                menor_id=uuid.UUID(menor_id),
                profesional_id=uuid.UUID(profesional_id),
                rol_asignado=rol_asignado,
            )
        )
        s.commit()
