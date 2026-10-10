"""Security primitives: passwords, tokens, API keys, encryption, MFA, auth seams."""

from finagent_api.security.api_keys import (
    GeneratedApiKey,
    extract_prefix,
    generate_api_key,
    hash_api_key,
    looks_like_api_key,
)
from finagent_api.security.auth_provider import AuthenticatedIdentity, AuthProvider, OAuthRegistry
from finagent_api.security.crypto import (
    decrypt_secret,
    encrypt_secret,
    mask_secret,
    sign_payload,
    verify_signature,
)
from finagent_api.security.mfa import (
    generate_recovery_codes,
    generate_totp_secret,
    provisioning_uri,
    verify_totp,
)
from finagent_api.security.passwords import (
    generate_password,
    hash_password,
    validate_password_strength,
    verify_password,
)
from finagent_api.security.tokens import (
    AccessTokenClaims,
    create_access_token,
    create_invitation_token,
    create_refresh_token,
    decode_access_token,
    hash_token,
    refresh_expiry,
)

__all__ = [
    "GeneratedApiKey",
    "extract_prefix",
    "generate_api_key",
    "hash_api_key",
    "looks_like_api_key",
    "AuthenticatedIdentity",
    "AuthProvider",
    "OAuthRegistry",
    "decrypt_secret",
    "encrypt_secret",
    "mask_secret",
    "sign_payload",
    "verify_signature",
    "generate_recovery_codes",
    "generate_totp_secret",
    "provisioning_uri",
    "verify_totp",
    "generate_password",
    "hash_password",
    "validate_password_strength",
    "verify_password",
    "AccessTokenClaims",
    "create_access_token",
    "create_invitation_token",
    "create_refresh_token",
    "decode_access_token",
    "hash_token",
    "refresh_expiry",
]
