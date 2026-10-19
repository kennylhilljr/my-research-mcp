# ADR 0003: Secrets live in the macOS Keychain; configuration holds references

- **Status:** Proposed (accepted when the owner approves PRD v1)
- **Date:** 2026-10-19

## Context

v1 reads API keys from environment variables, which the README tells users to paste into each client's config `env` block. On the owner's Mac that means three plaintext copies (OPS-11), readable through v1's SQL file-read hole (OPS-01). Keys also leak into tool output through URL query strings and raw exception text (OPS-04).

## Decision

Every secret is a Keychain generic password with service `research-mcp/<NAME>` and account set to the macOS user. Configuration files contain only references (`keychain:research-mcp/<NAME>`). Values are read once at daemon start into a `Secret` type whose text form shows only the name and a fingerprint, and only three platform modules reveal them (`platform/http.py`, `platform/mcp_client.py`, and `platform/auth.py`, which the shim, app and CLI use for the daemon token), attaching each to its own origin, in a header where possible. A redaction filter covers logs, errors, UI and notifications. Credential metadata (fingerprint, modification date, expiry, rotate-by date, validation result), never values, is stored in `state.db` to drive expiry notices. Keychain access goes through `/usr/bin/security`; writes pass the value on stdin (`security -i`), never in a process argument list. The daemon token and any notification webhook token are Keychain items too; the cursor signing key is derived from the daemon token. MCP clients never hold the daemon token: they all launch the stdio shim, which reads it from the Keychain.

## Consequences

- No plaintext secrets on disk; client configs carry none.
- Rotation is "update the Keychain item, press Reload" with no restart.
- Items written by `/usr/bin/security` trust that binary, so the daemon's reads do not prompt, even after Python upgrades. A locked Keychain (for example before first login) is reported once as `keychain_locked`, not as missing keys.
- Tests use a fake provider; CI never touches a Keychain.
