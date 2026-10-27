from fastapi import FastAPI
from sqlalchemy import text

from app.db import SessionLocal
from app.api.router import api_router


app = FastAPI(title="Codivis One CRM API")
app.include_router(api_router)


@app.get("/health")
def health() -> dict:
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    return {"status": "ok", "service": "crm-api"}
