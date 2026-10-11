"""API key generation and verification.

Format: ``fk_<env>_<prefix>_<secret>``. Only ``prefix`` and a SHA-256 hash of the whole key
are stored, so a leaked database cannot be used to call the API, and the plaintext key is
returned exactly once at creation.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

PREFIX_LENGTH = 8
SECRET_LENGTH = 32


@dataclass(frozen=True)
class GeneratedApiKey:
    plaintext: str
    prefix: str
    key_hash: str

    @property
    def masked(self) -> str:
        return f"{self.prefix}{'•' * 8}"


def generate_api_key(environment: str = "live") -> GeneratedApiKey:
    prefix = secrets.token_hex(PREFIX_LENGTH // 2)
    secret = secrets.token_urlsafe(SECRET_LENGTH)
    plaintext = f"fk_{environment}_{prefix}_{secret}"
    return GeneratedApiKey(plaintext=plaintext, prefix=prefix, key_hash=hash_api_key(plaintext))


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.strip().encode("utf-8")).hexdigest()


def extract_prefix(plaintext: str) -> str | None:
    parts = plaintext.strip().split("_")
    return parts[2] if len(parts) >= 4 and parts[0] == "fk" else None


def looks_like_api_key(value: str) -> bool:
    return value.strip().startswith("fk_")
