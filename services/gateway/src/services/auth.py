"""Authentication service using scrypt password hashing and HS256 JWT tokens."""

import base64
import hashlib
import hmac
import json
import os
import time
import uuid

from services.gateway.src.repositories.user_repo import UserRepository


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a random 16-byte salt."""
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored scrypt salt$digest."""
    try:
        salt_b64, digest_b64 = stored_hash.split("$", maxsplit=1)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except ValueError:
        return False
    actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(actual, expected)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def create_jwt(user_id: str, email: str, secret: str, ttl_seconds: int) -> str:
    """Create an HS256 JWT token."""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url_encode(
        json.dumps(
            {
                "sub": user_id,
                "email": email,
                "exp": int(time.time()) + ttl_seconds,
            }
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url_encode(sig)}"


def decode_jwt(token: str, secret: str) -> dict[str, str | int]:
    """Verify signature and expiration of an HS256 JWT token."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_sig, _b64url_decode(sig_b64)):
        raise ValueError("Invalid token signature")
    payload = json.loads(_b64url_decode(payload_b64))
    if not isinstance(payload, dict) or int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expired")
    return payload


class AuthService:
    """Register, authenticate, and verify users."""

    def __init__(self, repo: UserRepository, jwt_secret: str, jwt_ttl_seconds: int) -> None:
        self._repo = repo
        self._secret = jwt_secret
        self._ttl = jwt_ttl_seconds

    def register(self, email: str, password: str) -> tuple[str, str, str]:
        if self._repo.get_by_email(email) is not None:
            raise ValueError("Email already registered")
        user_id = f"u_{uuid.uuid4().hex[:10]}"
        row = self._repo.create_user(user_id, email, hash_password(password))
        token = create_jwt(row.id, row.email, self._secret, self._ttl)
        return row.id, row.email, token

    def login(self, email: str, password: str) -> tuple[str, str, str]:
        row = self._repo.get_by_email(email)
        if row is None or not verify_password(password, row.password_hash):
            raise ValueError("Invalid email or password")
        token = create_jwt(row.id, row.email, self._secret, self._ttl)
        return row.id, row.email, token

    def authenticate_token(self, token: str) -> str:
        payload = decode_jwt(token, self._secret)
        user_id = str(payload["sub"])
        if self._repo.get_by_id(user_id) is None:
            raise ValueError("User no longer exists")
        return user_id
