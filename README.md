# Backend

```
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
pytest
```
Documentación interactiva: `/docs`. Salud: `/api/v1/health`.
