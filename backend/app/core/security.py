"""Optional bearer-token authentication for the local API."""

from __future__ import annotations

import hmac

from app.core.config import get_settings
from fastapi import HTTPException, Request, status


def _supplied_token(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if header and header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    # EventSource cannot set headers; allow the query parameter for the SSE route.
    token = request.query_params.get("token")
    if token and request.url.path.endswith("/stream"):
        return token
    return None


async def require_api_token(request: Request) -> None:
    """Enforce AUTODEV_API_TOKEN when configured; otherwise allow local usage."""
    expected = get_settings().api_token
    if not expected:
        return
    supplied = _supplied_token(request)
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
