"""TOTP multi-factor authentication (RFC 6238).

Implemented directly against ``hmac``/``hashlib`` rather than adding a dependency for ~40
lines of well-specified code. Secrets are stored encrypted and never returned after
enrolment.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

DIGITS = 6
PERIOD_SECONDS = 30
#: Periods either side of now that are accepted (clock skew).
SKEW_PERIODS = 1


def generate_totp_secret(length: int = 20) -> str:
    return base64.b32encode(secrets.token_bytes(length)).decode("utf-8").rstrip("=")


def _hotp(secret_b32: str, counter: int) -> str:
    padding = "=" * (-len(secret_b32) % 8)
    key = base64.b32decode(secret_b32.upper() + padding, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**DIGITS)).zfill(DIGITS)


def current_totp(secret_b32: str, *, at: float | None = None) -> str:
    return _hotp(secret_b32, int((at if at is not None else time.time()) // PERIOD_SECONDS))


def verify_totp(secret_b32: str, code: str, *, at: float | None = None) -> bool:
    if not secret_b32 or not code:
        return False
    cleaned = code.strip().replace(" ", "")
    if len(cleaned) != DIGITS or not cleaned.isdigit():
        return False
    counter = int((at if at is not None else time.time()) // PERIOD_SECONDS)
    return any(
        hmac.compare_digest(_hotp(secret_b32, counter + offset), cleaned)
        for offset in range(-SKEW_PERIODS, SKEW_PERIODS + 1)
    )


def provisioning_uri(secret_b32: str, *, account: str, issuer: str) -> str:
    """otpauth:// URI for authenticator apps."""
    label = quote(f"{issuer}:{account}")
    return (
        f"otpauth://totp/{label}?secret={secret_b32}&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits={DIGITS}&period={PERIOD_SECONDS}"
    )


def generate_recovery_codes(count: int = 8) -> list[str]:
    return [
        f"{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(count)
    ]
