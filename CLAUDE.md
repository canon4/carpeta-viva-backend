# Backend (FastAPI, monolito modular)

Repositorio independiente dentro de Carpeta_Viva. La fuente de verdad del proyecto es `../CLAUDE.md`: contexto, módulos (`../docs/modulos.md`), decisiones (`../docs/adr/`) y plan (`../docs/plan-por-fases.md`).

- Módulos en `app/modules/<modulo>/` (`api`, `application`, `domain`, `repository`, `schemas`, `models`). Se comunican solo por la capa de aplicación.
- Todo bajo `/api/v1`. Tras cambiar endpoints: `python scripts/export_openapi.py` (actualiza `openapi.json`, contrato con el frontend).
- Migraciones primero: `alembic revision --autogenerate -m "..."` y `alembic upgrade head`.
- Pruebas: `pytest`. Solo datos sintéticos. Sin secretos en el código.
- Agente responsable: `backend`. Cambios que toquen datos de menores pasan por `seguridad`.
