# Automatic token refresh failure

The initial refresh implementation encrypted its GET query parameters but
omitted the `Encrypt: true` and `EncryptVersion: 2.0` headers. Login already
included these headers. TCL's Android account interceptor adds both headers to
the encrypted `/auth/auth/refershToken` request as well; the plaintext
`refreshToken` header and the intentionally misspelled endpoint are correct.

On the affected installation the access token expired on September 20 UTC,
while the refresh token remained valid until October 20 UTC. Refresh was being
attempted, not forgotten: the endpoint returned `InternalError` repeatedly.
Account locks, persistence and transient-error classification alone could not
correct this request format.

After adding the missing headers and restarting on October 3, ordinary startup
refresh rotated credentials and persisted the replacement refresh token to both
device entries. Its issue time was October 3, 13:46 UTC and expiry December 2,
13:46 UTC. No manual login or standalone token rotation was needed.

Transient refresh failures now have account-scoped exponential backoff, starting
at 30 seconds and capped at five minutes. Changed credentials/settings bypass
the backoff. An explicitly rejected access token is never retried when refresh
fails transiently, and transient failures never trigger reauthentication.

Regression coverage checks the encrypted request headers and shared-account
failure backoff, alongside existing rotation, persistence, hot-update and
authentication-rejection tests. Live state availability is separate from proof
that a physical control command was applied.
