"""Symmetric encryption for secrets at rest.

Provider credentials, MFA secrets and webhook signing secrets are encrypted with a Fernet
key derived from ``SECRET_KEY`` via HKDF. Rotating ``SECRET_KEY`` therefore invalidates
stored secrets by design — they must be re-entered, which is safer than leaving them
readable with an old key.
"""

from __future__ import annotations

import base64
import hmac
from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from finagent_api.settings import get_settings
from finagent_core.errors import FinagentError
from finagent_core.logging import get_logger

logger = get_logger(__name__)
_INFO = b"finagent-secret-encryption-v1"


def _fernet() -> Fernet:
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO).derive(
        get_settings().secret_key.encode("utf-8")
    )
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(plaintext: str) -> str:
    if plaintext is None:
        raise FinagentError("cannot encrypt None")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str | None) -> str | None:
    """Return the plaintext, or ``None`` when it cannot be decrypted (e.g. key rotated)."""
    if not ciphertext:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning("secret_decrypt_failed")
        return None


def mask_secret(plaintext: str, *, visible: int = 4) -> str:
    if not plaintext:
        return ""
    if len(plaintext) <= visible:
        return "•" * len(plaintext)
    return "•" * (len(plaintext) - visible) + plaintext[-visible:]


def sign_payload(payload: bytes, secret: str) -> str:
    """HMAC-SHA256 signature used for webhook delivery headers."""
    return hmac.new(secret.encode("utf-8"), payload, sha256).hexdigest()


def verify_signature(payload: bytes, secret: str, signature: str) -> bool:
    return hmac.compare_digest(sign_payload(payload, secret), signature)
