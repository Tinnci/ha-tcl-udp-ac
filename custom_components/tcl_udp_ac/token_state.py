"""
Access-token lifetime helpers.

Mirrors the TCL+ app's TokenManager logic: an access token should be refreshed
once it has passed 70% of its lifetime, and a refresh token is considered dead
once its ``exp`` is in the past. Both tokens are JWTs carrying ``exp``/``iat``.
"""

from __future__ import annotations

from .tcl_crypto import decode_jwt_claims

# The app refreshes once the access token passes 70% of its lifetime.
_REFRESH_FRACTION = 0.7


def _exp_iat(token: str) -> tuple[int, int] | None:
    claims = decode_jwt_claims(token)
    exp = claims.get("exp")
    iat = claims.get("iat")
    if exp is None or iat is None:
        return None
    try:
        return int(exp), int(iat)
    except (TypeError, ValueError):
        return None


def access_token_needs_refresh(token: str, now: float) -> bool:
    """
    Return True if the access token has passed 70% of its lifetime.

    Unparseable tokens are treated as needing refresh (the app does the same).
    """
    parsed = _exp_iat(token)
    if parsed is None:
        return True
    exp, iat = parsed
    threshold = iat + (exp - iat) * _REFRESH_FRACTION
    return threshold < now


def refresh_token_expired(token: str, now: float) -> bool:
    """Return True if the refresh token is missing/unparseable or past expiry."""
    if not token:
        return True
    parsed = _exp_iat(token)
    if parsed is None:
        return True
    exp, _iat = parsed
    return exp < now


def access_token_expired(token: str, now: float) -> bool:
    """Return True if the access token is missing/unparseable or past expiry."""
    if not token:
        return True
    parsed = _exp_iat(token)
    if parsed is None:
        return True
    exp, _iat = parsed
    return exp < now
