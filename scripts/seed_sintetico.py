"""Crea datos sintéticos de demo en la base de datos configurada en `.env`.

ADVERTENCIA: estos son datos 100% sintéticos y la contraseña es conocida
("demo12345"). Úsalo solo en desarrollo/demo. NUNCA correr contra una base
de datos de producción ni con datos reales de menores, madres sustitutas o
profesionales.

Seguro de ejecutar más de una vez: si un usuario, zona, hogar, madre o
profesional ya existe (por email/nombre/identificación), no lo duplica.

Crea:
- Usuarios con rol admin, coordinador, madre, profesional, defensor, auditor.
- Una Zona ("Zona 1 - Florencia").
- Un HogarSustituto en esa zona.
- Una MadreSustituta vinculada al usuario "madre" y asignada a ese hogar.
- Dos Profesional: uno psicosocial (usuario "profesional") y uno defensor (usuario "defensor").
- Un Menor ficticio ("Carlitos Sintético Demo") con asignación vigente a ese hogar,
  los dos profesionales asignados, y un permiso de expediente (sección "salud") otorgado
  por el defensor a la madre de demo, para poder probar RF7 y ADR-0007 de punta a punta.

Uso:
    python scripts/seed_sintetico.py
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from datetime import date  # noqa: E402

from app.core.database import get_engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.modules.asignaciones.models import Asignacion  # noqa: E402
from app.modules.auth.models import Usuario  # noqa: E402
from app.modules.madres.models import MadreSustituta  # noqa: E402
from app.modules.menores.models import Menor, PermisoExpediente  # noqa: E402
from app.modules.profesionales.models import MenorProfesional, Profesional  # noqa: E402
from app.modules.zonas_hogares.models import HogarSustituto, Zona  # noqa: E402

CLAVE_DEMO = "demo12345"

USUARIOS_DEMO = [
    ("admin@demo.local", "admin"),
    ("coordinador@demo.local", "coordinador"),
    ("madre@demo.local", "madre"),
    ("profesional@demo.local", "profesional"),
    ("defensor@demo.local", "defensor"),
    ("auditor@demo.local", "auditor"),
]


def obtener_o_crear_usuario(session: Session, email: str, rol: str) -> Usuario:
    usuario = session.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is None:
        usuario = Usuario(email=email, password_hash=hash_password(CLAVE_DEMO), rol=rol)
        session.add(usuario)
        session.flush()
        print(f"  creado usuario {email} ({rol})")
    else:
        print(f"  ya existía usuario {email}")
    return usuario


def obtener_o_crear_zona(session: Session, nombre: str) -> Zona:
    zona = session.scalar(select(Zona).where(Zona.nombre == nombre))
    if zona is None:
        zona = Zona(nombre=nombre, descripcion="Zona sintética de demostración")
        session.add(zona)
        session.flush()
        print(f"  creada zona {nombre}")
    else:
        print(f"  ya existía zona {nombre}")
    return zona


def obtener_o_crear_hogar(session: Session, zona: Zona) -> HogarSustituto:
    hogar = session.scalar(select(HogarSustituto).where(HogarSustituto.zona_id == zona.id))
    if hogar is None:
        hogar = HogarSustituto(zona_id=zona.id, capacidad_maxima=6, estado="activo")
        session.add(hogar)
        session.flush()
        print("  creado hogar sustituto de demo")
    else:
        print("  ya existía un hogar sustituto en esa zona")
    return hogar


def obtener_o_crear_madre(session: Session, usuario: Usuario, hogar: HogarSustituto) -> MadreSustituta:
    madre = session.scalar(select(MadreSustituta).where(MadreSustituta.usuario_id == usuario.id))
    if madre is None:
        madre = MadreSustituta(
            usuario_id=usuario.id,
            nombres="María",
            apellidos="Sintética Demo",
            numero_identificacion="1000000001",
            direccion="Calle Falsa 123, Florencia",
            telefono="3000000001",
            estado_certificacion="vigente",
        )
        session.add(madre)
        session.flush()
        print("  creada madre sustituta de demo")
    else:
        print("  ya existía la madre sustituta de demo")
    if hogar.madre_id is None:
        hogar.madre_id = madre.id
    return madre


def obtener_o_crear_profesional(
    session: Session, usuario: Usuario, cargo: str, nombres: str, numero_registro: str
) -> Profesional:
    profesional = session.scalar(select(Profesional).where(Profesional.usuario_id == usuario.id))
    if profesional is None:
        profesional = Profesional(
            usuario_id=usuario.id,
            nombres=nombres,
            apellidos="Profesional Demo",
            cargo=cargo,
            especialidad="Psicología" if cargo == "psicosocial" else None,
            numero_registro=numero_registro,
        )
        session.add(profesional)
        session.flush()
        print(f"  creado profesional de demo ({cargo})")
    else:
        print(f"  ya existía el profesional de demo ({cargo})")
    return profesional


def obtener_o_crear_menor(session: Session, hogar: HogarSustituto) -> Menor:
    """Menor 100% ficticio: solo para probar el módulo de expedientes en demo/desarrollo."""
    menor = session.scalar(select(Menor).where(Menor.numero_documento == "DEMO-0000001"))
    if menor is None:
        menor = Menor(
            nombres="Carlitos Sintético",
            apellidos="Demo",
            fecha_nacimiento=date(2016, 4, 1),
            genero="masculino",
            tipo_documento="registro_civil",
            numero_documento="DEMO-0000001",
            estado_actual="activo",
        )
        session.add(menor)
        session.flush()
        print("  creado menor ficticio de demo")
    else:
        print("  ya existía el menor ficticio de demo")

    asignacion = session.scalar(
        select(Asignacion).where(Asignacion.menor_id == menor.id, Asignacion.estado == "vigente")
    )
    if asignacion is None:
        asignacion = Asignacion(
            menor_id=menor.id,
            hogar_id=hogar.id,
            fecha_inicio=date(2026, 1, 1),
            estado="vigente",
            tipo_movimiento="ingreso",
            motivo="ingreso de demo",
        )
        session.add(asignacion)
        session.flush()
        print("  creada asignación (ingreso) de demo para el menor ficticio")
    else:
        print("  ya existía una asignación vigente para el menor ficticio")
    return menor


def vincular_profesional_a_menor(session: Session, menor: Menor, profesional: Profesional, rol_asignado: str) -> None:
    vinculo = session.scalar(
        select(MenorProfesional).where(
            MenorProfesional.menor_id == menor.id, MenorProfesional.profesional_id == profesional.id
        )
    )
    if vinculo is None:
        session.add(MenorProfesional(menor_id=menor.id, profesional_id=profesional.id, rol_asignado=rol_asignado))
        print(f"  asignado profesional ({rol_asignado}) al menor ficticio")
    else:
        print(f"  ya estaba asignado el profesional ({rol_asignado}) al menor ficticio")


def otorgar_permiso_salud_a_madre(
    session: Session, menor: Menor, madre: MadreSustituta, defensor: Profesional
) -> None:
    if madre.usuario_id is None or defensor.usuario_id is None:
        return
    permiso = session.scalar(
        select(PermisoExpediente).where(
            PermisoExpediente.menor_id == menor.id,
            PermisoExpediente.seccion == "salud",
            PermisoExpediente.usuario_id == madre.usuario_id,
        )
    )
    if permiso is None:
        session.add(
            PermisoExpediente(
                menor_id=menor.id,
                seccion="salud",
                usuario_id=madre.usuario_id,
                otorgado_por=defensor.usuario_id,
                notas="Permiso de demo otorgado por el defensor",
            )
        )
        print("  otorgado permiso de sección 'salud' a la madre de demo (por el defensor)")
    else:
        print("  ya existía el permiso de sección 'salud' para la madre de demo")


def sembrar() -> None:
    engine = get_engine()
    with Session(engine) as session:
        print("Usuarios:")
        usuarios = {email: obtener_o_crear_usuario(session, email, rol) for email, rol in USUARIOS_DEMO}

        print("Zona y hogar:")
        zona = obtener_o_crear_zona(session, "Zona 1 - Florencia")
        hogar = obtener_o_crear_hogar(session, zona)

        coordinador = usuarios["coordinador@demo.local"]
        if coordinador.zona_id is None:
            coordinador.zona_id = zona.id
            print("  asignada zona de demo al coordinador")
        else:
            print("  el coordinador ya tenía zona asignada")

        print("Madre sustituta:")
        madre = obtener_o_crear_madre(session, usuarios["madre@demo.local"], hogar)

        print("Profesionales:")
        psicosocial = obtener_o_crear_profesional(
            session, usuarios["profesional@demo.local"], "psicosocial", "Pedro", "DEMO-0001"
        )
        defensor = obtener_o_crear_profesional(
            session, usuarios["defensor@demo.local"], "defensor", "Diana", "DEMO-0002"
        )

        print("Menor ficticio y expediente:")
        menor = obtener_o_crear_menor(session, hogar)
        vincular_profesional_a_menor(session, menor, psicosocial, "psicosocial")
        vincular_profesional_a_menor(session, menor, defensor, "defensor")
        otorgar_permiso_salud_a_madre(session, menor, madre, defensor)

        session.commit()
    print(f"\nListo. Contraseña de todos los usuarios de demo: {CLAVE_DEMO}")


if __name__ == "__main__":
    sembrar()
