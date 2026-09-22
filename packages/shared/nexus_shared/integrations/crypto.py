"""AES-256-GCM Token and Credential Encryption Module for NEXUS."""

import base64
import hashlib
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from packages.config.nexus_config import get_settings


def _get_derived_key() -> bytes:
    """Derive a 256-bit (32-byte) key from the configured integration encryption key."""
    settings = get_settings()
    raw_key = getattr(
        settings,
        "integration_encryption_key",
        "nexus-integration-default-aes256-gcm-key-32b!",
    )
    # Use SHA-256 to ensure exactly 32 bytes
    return hashlib.sha256(raw_key.encode("utf-8")).digest()


def encrypt_credentials(payload: dict[str, Any] | str) -> str:
    """Encrypt dictionary or string credentials using AES-256-GCM.

    Returns:
        Base64-encoded string format: base64(nonce + ciphertext_and_tag)
    """
    key = _get_derived_key()
    aesgcm = AESGCM(key)

    if isinstance(payload, dict):
        plaintext = json.dumps(payload).encode("utf-8")
    else:
        plaintext = str(payload).encode("utf-8")

    # Standard 96-bit (12 bytes) nonce for GCM
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    combined = nonce + ciphertext
    return base64.b64encode(combined).decode("ascii")


def decrypt_credentials(encrypted_b64: str) -> dict[str, Any] | str:
    """Decrypt AES-256-GCM encrypted credentials string.

    Returns:
        Decoded dictionary if JSON, otherwise raw string.
    """
    if not encrypted_b64:
        return {}

    key = _get_derived_key()
    aesgcm = AESGCM(key)

    combined = base64.b64decode(encrypted_b64.encode("ascii"))
    if len(combined) < 12:
        raise ValueError("Invalid encrypted credential format: payload too short")

    nonce = combined[:12]
    ciphertext = combined[12:]

    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    plaintext_str = plaintext_bytes.decode("utf-8")

    try:
        return json.loads(plaintext_str)
    except json.JSONDecodeError:
        return plaintext_str
