from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/challenge")
def get_challenge():
    return {"message": "Challenge reached"}
