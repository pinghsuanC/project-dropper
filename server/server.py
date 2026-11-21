from contextlib import asynccontextmanager

from fastapi import FastAPI

from auth.routes import router as auth_router
from db.database_connection import DatabaseConnection
from devices.routes import router as device_router
from files.routes import router as file_router
from pairing.routes import router as pairing_router


@asynccontextmanager
async def lifespan(app):
    DatabaseConnection().init_db()
    yield
    # anything after yield runs on shutdown


app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)
app.include_router(file_router)
app.include_router(device_router)
app.include_router(pairing_router)
