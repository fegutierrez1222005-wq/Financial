"""Password hashing and policy."""

from __future__ import annotations

import re
import secrets

import bcrypt

from finagent_core.errors import ValidationFailedError

_COMMON_PASSWORDS = frozenset(
    {
        "password", "password1", "password123", "qwerty123456", "letmein12345",
        "changeme123", "administrator", "welcome12345", "iloveyou1234",
    }
)


def hash_password(password: str, *, rounds: int = 12) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-time verification.

    A missing hash still burns a comparison so response timing is similar for existing and
    non-existing accounts.
    """
    if not password_hash:
        bcrypt.checkpw(b"timing-equaliser", bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt(4)))
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def validate_password_strength(password: str, *, min_length: int = 12) -> None:
    """Raise :class:`ValidationFailedError` when a password is too weak."""
    problems: list[str] = []
    if len(password) < min_length:
        problems.append(f"must be at least {min_length} characters")
    if not re.search(r"[a-z]", password):
        problems.append("must contain a lowercase letter")
    if not re.search(r"[A-Z]", password):
        problems.append("must contain an uppercase letter")
    if not re.search(r"\d", password):
        problems.append("must contain a digit")
    if password.lower() in _COMMON_PASSWORDS:
        problems.append("is too common")
    if problems:
        raise ValidationFailedError(
            "password does not meet the policy", details={"requirements": problems}
        )


def generate_password(length: int = 20) -> str:
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))
