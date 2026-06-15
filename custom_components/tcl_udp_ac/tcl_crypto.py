"""
Cryptographic helpers for the TCL+ account API.

The TCL+ Android app encrypts request parameters sent to ``cn.account.tcl.com``
with RSA. It fetches a 1024-bit RSA public key from ``/auth/common/publicKey``
and encrypts each parameter value as ``RSA/ECB/PKCS1Padding``, chunking the
plaintext into 64-byte segments before encryption and base64-encoding the
concatenated ciphertext. This module mirrors that behaviour so the integration
can talk to the account API directly.

Device control on ``io.zx.tcljd.com`` is NOT encrypted; only the account/auth
endpoints require this.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_public_key

# The app chunks plaintext into 64-byte segments before RSA-encrypting each one.
_CHUNK_SIZE = 64


class TclCryptoError(Exception):
    """Raised when RSA key loading or encryption fails."""


def load_public_key(public_key_b64: str) -> object:
    """
    Load a base64 DER (X.509 SubjectPublicKeyInfo) RSA public key.

    The string returned by ``/auth/common/publicKey`` is the raw base64 of the
    DER encoding, without PEM armor.
    """
    cleaned = "".join(public_key_b64.split())
    try:
        der = base64.b64decode(cleaned)
        return load_der_public_key(der)
    except (binascii.Error, ValueError) as exc:
        msg = "Invalid TCL public key"
        raise TclCryptoError(msg) from exc


def encrypt_param(value: str, public_key: object) -> str:
    """
    Encrypt a single parameter value the way the TCL+ app does.

    Chunks the UTF-8 plaintext into 64-byte segments, RSA/PKCS1v15-encrypts each
    segment, concatenates the ciphertext blocks, and base64-encodes the result.
    """
    data = value.encode("utf-8")
    out = bytearray()
    for start in range(0, len(data), _CHUNK_SIZE):
        chunk = data[start : start + _CHUNK_SIZE]
        out += public_key.encrypt(chunk, padding.PKCS1v15())
    return base64.b64encode(bytes(out)).decode("ascii")


def md5_password(password: str) -> str:
    """Return the lowercase hex MD5 of a password (TCL password-login format)."""
    return hashlib.md5(password.encode("utf-8")).hexdigest()  # noqa: S324


def decode_jwt_claims(token: str) -> dict:
    """
    Decode the unverified payload claims of a JWT.

    The TCL access/refresh tokens are RS256 JWTs. We only need to read the
    ``exp``/``iat`` claims to decide when to refresh; we do not verify the
    signature (the server does that).
    """
    parts = token.split(".")
    if len(parts) < 2:  # noqa: PLR2004
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload)
        return json.loads(raw)
    except (binascii.Error, ValueError, json.JSONDecodeError):
        return {}
