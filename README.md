# Financial Data Management System (FDMS)

Production-ready MVP to pull, validate, and manage financial data for investment bankers/brokerages.

## Stack
- Backend: FastAPI, SQLAlchemy, Alembic, Celery, Redis, PostgreSQL
- Frontend: React + TypeScript + Vite
- Infra: Docker Compose, Nginx

## Quick start
1. Copy envs: `cp .env.example .env`
2. Build and run: `docker compose up --build`
3. Backend API: `http://localhost/api/v1` (docs at `/docs`)
4. Frontend: `http://localhost`

## Local backend without Docker
```
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python scripts/init_db.py
python scripts/create_admin.py
uvicorn main:app --reload
```

## Seed data
```
cd backend
python scripts/seed_data.py
```

## Testing
```
cd backend
pytest
```

## Notes
- External API clients use sandbox/mock responses. Add real keys and endpoints before production.
- CORS allows `http://localhost:5173` by default; adjust in `.env` if needed.

