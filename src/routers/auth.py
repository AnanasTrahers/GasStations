from fastapi import APIRouter, Depends

from src.config import business_settings
from src.dependencies import get_db_repo
from src.repositories import DBRepository
from src.schemas import AuthResponse, GoogleAuthRequest
from src.security import verify_google_token, create_access_token
from src.utils.logs import Logger

router = APIRouter(tags=["Auth"])


@router.post("/auth/google", response_model=AuthResponse)
async def google_auth(
        data: GoogleAuthRequest,
        db_repo: DBRepository = Depends(get_db_repo)
):
    Logger.info("Logging in with Google id...")
    google_data = verify_google_token(data.token)

    google_id = google_data.get("sub")
    email = google_data.get("email")

    user = await db_repo.users.get_by_google_id(google_id)
    if not user:
        user = await db_repo.users.create(google_id, email)

    access_token = create_access_token(user.id, business_settings.JWT_TTL_DAYS)

    Logger.info("Successfully logged in with Google id...")
    return AuthResponse(access_token=access_token)
