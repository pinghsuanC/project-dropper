import os
from contextlib import asynccontextmanager

import dotenv
from fastapi import FastAPI, HTTPException

from auth.routes import router as auth_router
from db.database_connection import DatabaseConnection
from devices.routes import router as device_router
from files.routes import router as file_router
from pairing.routes import router as pairing_router
from schemas.app import HealthResponse

dotenv.load_dotenv()
ENABLE_DOCS = os.getenv("APP_ENV").lower() != "prod"


@asynccontextmanager
async def lifespan(app):
    DatabaseConnection().init_db()
    yield
    # anything after yield runs on shutdown


app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)


app.include_router(auth_router)
app.include_router(file_router)
app.include_router(device_router)
app.include_router(pairing_router)


@app.get("/health", response_model=HealthResponse)
def health():
    try:
        with DatabaseConnection() as conn:
            conn.execute("SELECT 1")
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ok"}
