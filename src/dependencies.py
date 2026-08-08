import httpx
import jwt
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.config import project_settings
from src.database import get_db
from src.repositories import DBRepository
from src.utils.logs import Logger

security = HTTPBearer()


def get_httpx_client(request: Request) -> httpx.AsyncClient:
    return getattr(request.state, "httpx_client")


def get_redis(request: Request) -> Redis:
    return getattr(request.state, "redis_client")


def get_db_repo(session: AsyncSession = Depends(get_db)) -> DBRepository:
    return DBRepository(session)


def get_current_user_id(
        credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            project_settings.JWT_SECRET_KEY,
            algorithms=[project_settings.JWT_SIGNING_ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise ValueError("Sub claim missing in JWT")
        return user_id
    except InvalidTokenError as e:
        Logger.error(f"JWT validation failed", error=e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
