from dotenv import load_dotenv
from fastapi import FastAPI

from auth.routes import router as auth_router
from data.routes import router as data_router

load_dotenv()
app = FastAPI()
app.include_router(auth_router)
app.include_router(data_router)


@app.get("/")
def get_test():
    return {"message": "You have reached the test endpoint!"}
