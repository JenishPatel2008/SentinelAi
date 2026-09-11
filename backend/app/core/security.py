import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


AUTH_SECRET = os.getenv("SENTINEL_AUTH_SECRET", "sentinel-local-development-secret")
OPERATOR_USERNAME = os.getenv("SENTINEL_OPERATOR_USERNAME", "operator")
OPERATOR_PASSWORD = os.getenv("SENTINEL_OPERATOR_PASSWORD", "sentinel")
TOKEN_TTL_SECONDS = 8 * 60 * 60
bearer_scheme = HTTPBearer(auto_error=False)


def _encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(subject=OPERATOR_USERNAME):
    payload = {"sub": subject, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    body = _encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_encode(signature)}"


def verify_access_token(token):
    if not token or "." not in token:
        return None
    body, encoded_signature = token.split(".", 1)
    expected = hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    try:
        received = _decode(encoded_signature)
        payload = json.loads(_decode(body))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not hmac.compare_digest(received, expected) or payload.get("exp", 0) < time.time():
        return None
    if payload.get("sub") != OPERATOR_USERNAME:
        return None
    return payload


def authenticate_operator(username, password):
    return hmac.compare_digest(username or "", OPERATOR_USERNAME) and hmac.compare_digest(password or "", OPERATOR_PASSWORD)


def unauthorized():
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})


def get_current_operator(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    payload = verify_access_token(credentials.credentials if credentials else None)
    if payload is None:
        raise unauthorized()
    return payload


def get_stream_operator(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token: str | None = Query(default=None),
):
    payload = verify_access_token(credentials.credentials if credentials else token)
    if payload is None:
        raise unauthorized()
    return payload
