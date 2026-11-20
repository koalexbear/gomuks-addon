# Multiuser setup and acceptance tests

Version 0.4.0 provides one gomuks process and one persistent root per authenticated Home Assistant user. It is experimental and intended for initial testing on the HA test instance.

## Configuration

```yaml
public_origins:
  - "https://ha.example.com"
allowed_user_ids: []
max_instances: 4
legacy_owner_id: ""
```

- `public_origins`: exact HTTPS addresses of **Home Assistant**, no path/trailing slash. Multiple addresses can be listed. The origin is not inferred from untrusted request headers.
- `allowed_user_ids`: empty allows every authenticated HA-Ingress user to use their own instance; otherwise only listed exact HA IDs are admitted. No username-based routing and no shared default account.
- `max_instances`: simultaneously running gomuks backends, between 1 and 16. They start on first access and stay running until add-on shutdown or process failure. At capacity additional users get 503. No idle eviction or disk quota yet.
- `legacy_owner_id`: exact HA ID that owns any existing single-user data. Leave empty for a new installation with no `/data/gomuks` directory.

The old `public_origin` and `allowed_user_id` are accepted only as upgrade fallbacks for the origin list and the legacy owner. The previous single-user ID does not restrict multiuser access: use `allowed_user_ids` for admission.

Remove `enable_calls` and `desktop` from saved options. They are no longer supported. Microphone, camera and screen sharing remain blocked. The bundled Element Call path is blocked; upstream UI controls may still be visible. No native desktop listener or desktop credentials remain. Remove/disable any old NPM desktop proxy entry.

## Migration from single-user versions

1. Stop the existing add-on and create a backup including its private data. Confirm you can restore it; do not rely on downgrading the image after migration.
2. Record the current owner's HA ID, and set `legacy_owner_id` to it. Existing saved `allowed_user_id` is a fallback if not explicitly replaced.
3. Update the same add-on, rather than uninstalling it. At startup the legacy root `/data/gomuks` is atomically renamed to `/data/users/<owner-id>/gomuks`. The moved configuration's old absolute paths are rewritten when the owner's instance starts.
4. Missing/invalid owner or an existing destination causes startup to stop without overwriting data. No first visitor can claim the old account.
5. Verify the original owner retains their Matrix login, device and history. A second HA user must start with a separate blank Matrix login.

A local add-on and a repository-installed add-on have different HA identifiers and data directories. That transition does not move data automatically; retain the local installation and backup until a deliberate offline migration or new Matrix-device login/recovery has been tested. Never run two copies of the same Matrix crypto store.

## Data and security model

Each user's persistent root is `/data/users/<ha-user-id>/gomuks`, with separate config, data, crypto store, cache and logs. IDs are validated before directories are created. The proxy accepts only the Supervisor TCP peer `172.30.32.2`, whose trusted `X-Remote-User-Id` selects the backend. Missing, malformed or disallowed identities fail closed. Client-supplied backend cookies/Authorization headers cannot select another backend; they are stripped. The per-user credentials returned by the loopback-only auth manager never appear in frontend responses.

Each request, including media, SSE, uploads and WebSocket handshakes, goes through the selector. No public endpoint lets clients provide a backend port or data-root path. Instance ports are loopback only; only Ingress port 8099 listens internally. No host ports, host networking, Supervisor API or filesystem mounts are added.

All processes run in one trusted container: this is application-level account separation, not OS/container isolation between hostile users. Host and HA administrators can read all keys and decrypted content. Backups contain every user and need encryption and access control. Deleted HA users' data is retained until an administrator deliberately removes it offline. Never delete a database as a way to free a running slot.

A running WebSocket is authorized when opened. Allowlist changes take effect after add-on restart, which terminates existing connections. Logout/HA session expiration behavior must also be tested on the actual Supervisor. A backend crash affects that user's active connection and restarts on the next request. At capacity, restart the add-on or increase the limit after checking resources.

## Automated verification

From the repository root:

```sh
docker build --build-arg BUILD_ARCH=amd64 -t gomuks-ha:multiuser gomuks_web
docker run --rm --network none --entrypoint python3 \
  -v "$PWD/tests:/tests:ro" gomuks-ha:multiuser -m unittest discover -s /tests -v
docker run --rm --network none --entrypoint python3 \
  -v "$PWD/tests:/tests:ro" gomuks-ha:multiuser /tests/multiuser_smoke.py
```

The build requires network access. Tests run without external network access and publish no ports. The multiuser smoke test verifies routing through nginx against identity-reporting fixtures, then starts two real gomuks binaries with independent roots and restarts one after a full pool shutdown. It does not log in to Matrix or prove message-level E2EE isolation.

## Required HA acceptance

Use two separate browser profiles and two distinct HA users, A and B. Use two distinct Matrix test accounts; do not clone a Matrix device database.

1. A opens Ingress and logs into Matrix account A; B opens the same add-on and sees a fresh login, then logs into account B. Verify both devices against trusted clients.
2. Send different test messages and encrypted attachments in separate rooms. B must not see A's rooms/history/files and vice versa. Test simultaneous live updates, uploads, SSE fallback and WebSocket reconnects.
3. Reload, restart the add-on and restart HA. Each user must retain their own Matrix account/device and decrypt their own prior messages and attachments.
4. Limit `allowed_user_ids` to A, restart, and confirm B is denied while B's data is preserved. Remove the restriction again and confirm B returns to their own account.
5. Set `max_instances` to 1 and restart. A opens first, B receives 503 and never A's UI/data. Restart and reverse the order. Restore the intended capacity afterward.
6. Anonymous/direct network access and spoofed forwarded identity must fail. No host ports may be published. Embedded call resources should return 404; microphone/camera remain blocked.
7. Test legacy migration from a stopped single-user fixture. Opening as B first must not assign A's old data to B. Verify missing owner stops startup and conflicting destination never overwrites files.
8. Back up the stopped multiuser add-on and restore it on an isolated test installation. Do not keep original and restored Matrix device identities online together. Both accounts must retain their own keys and readable history.
9. Test long-running sessions, mobile layouts, browser account switching, logout, storage growth and resource usage. Use permitted personal networks; company/VPN access is not assumed.

Do not publish unredacted Ingress URLs, auth headers, cookies, logs or real user IDs when reporting failures. The compact ingress diagnostic logs decision flags, not raw IDs/headers; upstream backend logs may still contain sensitive metadata.

## Sources

- [HA-Ingress identity and network trust](https://contributors.home-assistant.io/apps/guides/ingress/)
- [gomuks single-account instances and storage](https://docs.mau.fi/gomuks/faq.html)
- [gomuks upstream source used by this image](https://github.com/gomuks/gomuks/tree/b1ba2099e9d4c0068c7e614d7141b001848369c5)
