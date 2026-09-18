"""
NEXUS Security & Cryptographic Utilities
Password hashing via bcrypt and access token generation/validation via PyJWT
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from packages.config.nexus_config import get_settings


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt with a generated salt."""
    pw_bytes = plain_password.encode("utf-8")
    if len(pw_bytes) > 72:
        raise ValueError("Password cannot be longer than 72 bytes")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        pw_bytes = plain_password.encode("utf-8")
        if len(pw_bytes) > 72:
            return False
        return bcrypt.checkpw(
            pw_bytes,
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    user_id: str,
    email: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token for user authentication."""
    settings = get_settings()
    now = datetime.now(UTC)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=settings.session_expiry_hours)

    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": "nexus-auth",
    }

    token = jwt.encode(payload, settings.encryption_key, algorithm="HS256")
    return token


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a signed JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.encryption_key,
            algorithms=["HS256"],
            issuer="nexus-auth",
        )
        return payload
    except jwt.PyJWTError:
        return None
