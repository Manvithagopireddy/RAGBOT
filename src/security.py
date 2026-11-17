"""
security.py — Authentication, Authorization, and Security Utilities.

Features:
  - Password hashing and verification using bcrypt.
  - JWT token generation and validation using PyJWT.
  - Rate limiting (in-memory sliding window / token bucket).
  - HTML escaping for user inputs to prevent XSS.
"""
import html
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import bcrypt
import jwt

from src.logger import get_logger

logger = get_logger(__name__)

# Security settings
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "ragbot-insecure-dev-secret-change-in-production-2026")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours


# ── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt with salt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as exc:
        logger.warning(f"Password verification error: {exc}")
        return False


# ── JWT Authentication ────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    username: str,
    role: str = "user",
    expires_delta: Optional[timedelta] = None
) -> str:
    """Generates a signed JWT access token."""
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a JWT access token. Returns payload or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT token has expired.")
        return None
    except jwt.InvalidTokenError as exc:
        logger.debug(f"Invalid JWT token: {exc}")
        return None


# ── XSS & Input Sanitization ──────────────────────────────────────────────────

def sanitize_html(text: str) -> str:
    """Escapes HTML entities in dynamic text to prevent XSS."""
    if not text:
        return ""
    return html.escape(text)


# ── Rate Limiter (In-Memory Sliding Window) ────────────────────────────────────

class InMemoryRateLimiter:
    """
    Sliding-window in-memory rate limiter per client IP or user ID.
    Default: 60 requests per minute.
    """
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.window = 60.0  # seconds
        # key -> list of timestamps
        self._history: Dict[str, list[float]] = {}

    def is_allowed(self, client_key: str) -> Tuple[bool, int]:
        """
        Checks if client_key has remaining request quota.
        Returns (is_allowed, remaining_seconds_to_wait).
        """
        now = time.time()
        cutoff = now - self.window

        timestamps = self._history.get(client_key, [])
        # Prune older than cutoff
        valid_timestamps = [ts for ts in timestamps if ts > cutoff]

        if len(valid_timestamps) >= self.rpm:
            earliest = valid_timestamps[0]
            retry_after = int(self.window - (now - earliest)) + 1
            self._history[client_key] = valid_timestamps
            return False, max(1, retry_after)

        valid_timestamps.append(now)
        self._history[client_key] = valid_timestamps
        return True, 0


# Global rate limiter instance
rate_limiter = InMemoryRateLimiter(requests_per_minute=int(os.environ.get("RATE_LIMIT_RPM", "60")))
