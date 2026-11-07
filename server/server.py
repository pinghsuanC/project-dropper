from contextlib import asynccontextmanager

from fastapi import FastAPI

from auth.routes import router as auth_router
from db.database_connection import DatabaseConnection


@asynccontextmanager
async def lifespan(app):
    DatabaseConnection().init_db()
    yield
    # anything after yield runs on shutdown


app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)
