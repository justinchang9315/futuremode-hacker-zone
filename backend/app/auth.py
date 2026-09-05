import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Literal

from app.config import Settings
from app.exceptions import UnauthorizedError

TokenRole = Literal["session", "guardian"]


@dataclass(frozen=True)
class AccessClaims:
    session_id: str
    child_id: str
    role: TokenRole
    expires_at: int


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(
    *,
    session_id: str,
    child_id: str,
    role: TokenRole,
    settings: Settings,
) -> tuple[str, int]:
    expires_at = int(time.time()) + settings.access_token_minutes * 60
    payload = json.dumps(
        {
            "session_id": session_id,
            "child_id": child_id,
            "role": role,
            "expires_at": expires_at,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = _encode(payload)
    secret = settings.app_secret_key.get_secret_value().encode("utf-8")
    signature = _encode(hmac.new(secret, encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}", expires_at


def verify_access_token(
    token: str,
    *,
    settings: Settings,
    expected_role: TokenRole | None = None,
    session_id: str | None = None,
    child_id: str | None = None,
) -> AccessClaims:
    try:
        encoded, supplied_signature = token.split(".", 1)
        secret = settings.app_secret_key.get_secret_value().encode("utf-8")
        expected_signature = _encode(
            hmac.new(secret, encoded.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError
        payload = json.loads(_decode(encoded))
        claims = AccessClaims(
            session_id=str(payload["session_id"]),
            child_id=str(payload["child_id"]),
            role=payload["role"],
            expires_at=int(payload["expires_at"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise UnauthorizedError("存取憑證無效，請由家長重新開始學習階段。") from exc

    if claims.expires_at < int(time.time()):
        raise UnauthorizedError("學習階段憑證已過期，請由家長重新開始。")
    if expected_role and claims.role != expected_role:
        raise UnauthorizedError("這個操作需要家長憑證。")
    if session_id and claims.session_id != session_id:
        raise UnauthorizedError("憑證與學習階段不相符。")
    if child_id and claims.child_id != child_id:
        raise UnauthorizedError("憑證與孩童資料不相符。")
    return claims
