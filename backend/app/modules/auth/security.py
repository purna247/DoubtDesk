import base64
import hashlib
import hmac
import secrets
import struct
import time
from typing import Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from app.config import get_settings

settings = get_settings()
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash password using Argon2id with cryptographically secure salt."""
    return _hasher.hash(password)


def verify_password(hash_value: str, password: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return _hasher.verify(hash_value, password)
    except (VerifyMismatchError, Exception):
        return False


def generate_opaque_token() -> str:
    """Generate high-entropy random URL-safe token for session cookies."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Compute SHA-256 hash of token to store in database (never store raw tokens)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------
# RFC 6238 Time-Based One-Time Password (TOTP) Implementation
# ------------------------------------------------------------------------------

def generate_totp_secret() -> str:
    """Generate a random base32 encoded secret for TOTP authenticator enrollment."""
    random_bytes = secrets.token_bytes(20)  # 160 bits recommended by RFC 6238
    return base64.b32encode(random_bytes).decode("utf-8")


def get_totp_code(secret_b32: str, timestamp: Optional[int] = None, time_step: int = 30) -> str:
    """
    Compute current 6-digit TOTP code according to RFC 6238.
    Default interval: 30 seconds.
    """
    if timestamp is None:
        timestamp = int(time.time())

    counter = timestamp // time_step
    # Pad base32 secret if needed
    padding_needed = (8 - len(secret_b32) % 8) % 8
    key = base64.b32decode(secret_b32 + "=" * padding_needed, casefold=True)

    counter_bytes = struct.pack(">Q", counter)
    hmac_digest = hmac.new(key, counter_bytes, hashlib.sha1).digest()

    offset = hmac_digest[-1] & 0x0F
    code_int = struct.unpack(">I", hmac_digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = code_int % 1000000
    return f"{code:06d}"


def verify_totp_code(
    secret_b32: str, code: str, valid_window: int = 1, time_step: int = 30
) -> bool:
    """
    Verify TOTP code with drift tolerance window (+/- valid_window intervals).
    """
    if len(code) != 6 or not code.isdigit():
        return False

    current_time = int(time.time())
    for drift in range(-valid_window, valid_window + 1):
        test_time = current_time + (drift * time_step)
        if hmac.compare_digest(get_totp_code(secret_b32, test_time, time_step), code):
            return True
    return False


# ------------------------------------------------------------------------------
# Signed Password Reset Tokens
# ------------------------------------------------------------------------------

def generate_password_reset_token(
    user_id: str,
    credential_version: int = 0,
    expires_in_seconds: int = 3600,
) -> str:
    """
    Generate cryptographically signed, tamper-proof, time-limited reset token.
    The credential version makes the token single-use without storing raw tokens.
    Format: base64(user_id:expiry:credential_version:signature)
    """
    expiry = int(time.time()) + expires_in_seconds
    payload = f"{user_id}:{expiry}:{credential_version}"
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    raw = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def verify_password_reset_token(token: str) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Verify reset token signature and expiry.
    Returns (is_valid, user_id, credential_version).
    """
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = raw.split(":")
        if len(parts) != 4:
            return False, None, None

        user_id, expiry_str, version_str, received_sig = parts
        expiry = int(expiry_str)
        credential_version = int(version_str)

        if time.time() > expiry:
            return False, None, None

        payload = f"{user_id}:{expiry}:{credential_version}"
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, received_sig):
            return False, None, None

        return True, user_id, credential_version
    except Exception:
        return False, None, None

