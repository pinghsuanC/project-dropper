from contextlib import asynccontextmanager

from auth.routes import router as auth_router
from db.database_connection import DatabaseConnection
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app):
    DatabaseConnection().init_db()
    yield
    # anything after yield runs on shutdown


app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)
