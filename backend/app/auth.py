import os
from functools import lru_cache

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

bearer = HTTPBearer(auto_error=False)


@lru_cache
def _auth_client() -> Client | None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication is required.")
    client = _auth_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    try:
        response = client.auth.get_user(credentials.credentials)
        user = getattr(response, "user", None)
        user_id = getattr(user, "id", None)
        if not user_id:
            raise ValueError("No authenticated user was returned.")
        return {
            "id": str(user_id),
            "email": getattr(user, "email", None),
            "user_metadata": getattr(user, "user_metadata", {}) or {},
        }
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.") from exc
