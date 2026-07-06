from fastapi import Request
import httpx


def get_httpx_client(request: Request) -> httpx.AsyncClient:
    return getattr(request.state, "httpx_client")
