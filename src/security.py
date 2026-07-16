from datetime import datetime, timezone, timedelta
from typing import Mapping, Any

import jwt
from fastapi import HTTPException, status
from google.auth.transport import requests
from google.oauth2 import id_token

from src.config import project_settings
from src.utils.logs import Logger


def verify_google_token(token: str) -> Mapping[str, Any]:
    try:
        Logger.info("Verifying Google token...")
        return id_token.verify_oauth2_token(
            token,  # type: ignore
            requests.Request(),
            project_settings.GOOGLE_CLIENT_ID,
        )

    except ValueError as e:
        Logger.error(f"Invalid Google token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )


def create_access_token(user_id: str, ttl_days) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=ttl_days)
    to_encode = {"sub": str(user_id), "exp": exp}

    return jwt.encode(
        to_encode,
        project_settings.SECRET_KEY,
        algorithm=project_settings.JWT_SIGNING_ALGORITHM
    )
