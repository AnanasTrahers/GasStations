from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.config import LOG_ID
from src.utils.order import get_uuid_str


class LogIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = get_uuid_str()
        token = LOG_ID.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            LOG_ID.reset(token)
