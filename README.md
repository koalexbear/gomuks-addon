# gomuks Web for Home Assistant

Multiuser Matrix chat for Home Assistant OS. Each authenticated HA-Ingress user gets a separate gomuks backend, Matrix login, database and encryption-key store.

**Version 0.4.0 is experimental.** Multiuser routing is tested in an isolated container; real HA sessions with two Matrix accounts, upgrades and backup/restore still need acceptance on a test instance.

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fkoalexbear%2Fgomuks-addon)

## What changed in 0.4.0

- A private gomuks instance starts on demand for each HA user. The Supervisor-provided user ID selects the instance on every request, including WebSockets and media.
- Calls and the native desktop endpoint have been removed from the add-on. Microphone, camera and screen capture remain blocked, and the bundled Element Call path returns 404. Upstream gomuks may still show call controls; this add-on does not support them.
- No desktop credentials, proxy hostname or additional listener to configure. HA-Ingress is the only route.
- Multiple explicit HA HTTPS origins are supported. No arbitrary Origin or forwarded identity is trusted.

## Install

1. In HA, open **Settings → Apps/Add-ons → App/Add-on Store → ⋮ → Repositories**.
2. Add `https://github.com/koalexbear/gomuks-addon`. The Supervisor must be able to read the repository; private GitHub repositories need separate authentication.
3. Install **gomuks Web (private ingress)**. The image is built on your HA device and needs network access to the upstream registry and Alpine repositories.
4. Configure:

   ```yaml
   public_origins:
     - "https://ha.example.com"
   allowed_user_ids: []
   max_instances: 4
   legacy_owner_id: ""
   ```

5. Start the add-on and open its web UI. Each HA user signs in to their own Matrix account and verifies their new Matrix device using a trusted client.

`public_origins` lists the exact HTTPS addresses used to open **Home Assistant**, including any explicit port, without paths or trailing slashes. These are not Matrix homeserver addresses. Add a second origin only if you actually use it. A consistent hostname with split DNS also works for LAN access.

An empty `allowed_user_ids` list permits **all authenticated HA-Ingress users**, including non-admin users, to use their own instance. For restricted access, list their exact 32-character lowercase HA IDs. This list is an admission rule; it never selects a shared Matrix account. Missing or malformed identities are always denied.

## Upgrading an existing single-user installation

**Back up the stopped add-on before updating. Migration moves its data directory; downgrading requires restoring the pre-update backup. Test this first on a disposable test installation.**

1. Keep the existing add-on installed. Record the HA user ID that owns its current Matrix account.
2. Update to 0.4.0, set `public_origins`, and set `legacy_owner_id` to that exact owner ID. The previous `allowed_user_id`, if still present in saved options, is accepted as a migration fallback. The old `public_origin` is also accepted as an origin fallback.
3. Remove old `enable_calls` and `desktop` options from saved YAML. Remove/disable any old NPM desktop proxy host as well; port 8098 is no longer served.
4. Start. `/data/gomuks` is moved to `/data/users/<owner-id>/gomuks`. Existing files are not copied to other users. Absolute paths in the old gomuks configuration are updated when its owner's backend starts.
5. If the owner is missing, invalid, or both old and destination data exist, startup stops. It never assigns an existing account to the first visitor or overwrites a destination.
6. Open as the original owner and confirm the existing Matrix device, history and decryption. Open as a different HA user: they must get their own fresh Matrix login, not the owner's account.

The deprecated `allowed_user_id` is **migration metadata only** in 0.4.0. It does not retain the old single-user admission restriction. Use `allowed_user_ids` to limit who may create/use an instance.

Moving from `/addons` to a GitHub-installed add-on is a different operation: HA assigns another add-on identifier and a separate data directory. Adding this repository does not automatically transfer a local add-on's data. Keep the old installation and backup until a deliberate migration or new Matrix-device login/recovery has been verified. Never run two copies of one Matrix crypto database simultaneously.

## Isolation, persistence and limits

Persistent data is stored under `/data/users/<ha-user-id>/gomuks`, including each user's config, database/keys, cache and logs. User IDs must match the strict ID format before any path or process is created. Internal credentials are random and unique per backend start; the proxy strips browser cookies and authorization headers and injects only the selected backend's credentials. Backend cookies are not returned to browsers.

Only port 8099 listens on the internal add-on network and it accepts the Supervisor at `172.30.32.2` only. The auth manager and individual backends use loopback. No host ports, host networking, Supervisor API permission or additional filesystem mounts are enabled.

Instances stay running after the user closes the UI. `max_instances` limits simultaneously running backends (default 4, range 1–16). At capacity, another user's request returns 503 without creating their directory or reusing anyone else's instance. Restarting the add-on frees all running slots while retaining data. A crashed backend can restart on its next request. Plan CPU, RAM and storage for one gomuks process per active user; there is no automatic idle eviction or per-user disk quota yet.

**This is application-level separation inside one trusted container, not a container sandbox per user.** Administrators and the add-on process can access all users' encryption keys and decrypted data. Encrypt backups, restrict host/admin access, and test recovery. A user removed from an allowlist needs an add-on restart to terminate their existing connections. Deleted HA users' stored directories are not automatically removed. Use separate browser profiles for the initial multiuser acceptance test to avoid stale page state when switching accounts.

## Updates

Increase `version` in `gomuks_web/config.yaml`, upload changes to GitHub, refresh the HA store and update the existing repository-installed add-on. A push alone does not update a running container. Do not uninstall to update.

## Create your own appearance

This repository does not ship themes. Create and maintain your personal CSS outside the repository, then paste it into gomuks **Custom CSS**. No add-on rebuild is required.

1. Open gomuks settings and find **Custom CSS**. Save a copy of any existing customization before replacing it.
2. Choose your own palette, font, spacing and corner radii. To match a Home Assistant theme, copy its relevant color values manually; HA theme variables do not automatically propagate into gomuks or synchronize with its user profile.
3. Start by overriding gomuks' CSS custom properties on `:root`: `--background-color`, `--text-color`, `--secondary-text-color`, `--primary-color`, `--border-color`, `--composer-background-color` and the room-list background properties. Consult the [stylesheet for the gomuks version used by this add-on](https://github.com/gomuks/gomuks/blob/b1ba2099e9d4c0068c7e614d7141b001848369c5/web/src/index.css) for available variables.
4. For layout changes, inspect the actual elements in your browser's developer tools. Scope rules to the relevant gomuks components. Adjust typography, padding and rounded surfaces without hiding errors, delivery states, unread indicators or keyboard focus. Preserve the room-list row heights because gomuks uses list virtualization.
5. Choose a fixed light/dark mode or follow the browser/system preference. If using CSS `light-dark()`, set the appropriate `color-scheme`. This choice is independent of the HA profile.
6. Apply the CSS and test desktop and mobile layouts, long messages, attachments, replies, unread states and keyboard navigation. Recheck after gomuks updates because selectors may change. Remove the added CSS to revert.

Keep a personal backup outside Git. The root `themes/` directory is ignored to prevent local theme files from being uploaded accidentally. Prefer local system fonts and avoid external imports when you want to keep the customization self-contained. Custom CSS changes presentation only; it does not change account isolation or access control.

## Tests

```sh
docker build --build-arg BUILD_ARCH=amd64 -t gomuks-ha:multiuser gomuks_web
docker run --rm --network none --entrypoint python3 \
  -v "$PWD/tests:/tests:ro" gomuks-ha:multiuser -m unittest discover -s /tests -v
docker run --rm --network none --entrypoint python3 \
  -v "$PWD/tests:/tests:ro" gomuks-ha:multiuser /tests/multiuser_smoke.py
```

Use `BUILD_ARCH=aarch64` with an appropriate builder for ARM64. Unit tests needing bcrypt run in the built image. `python3 -m unittest discover -s tests -v` also runs the settings tests locally and skips instance tests if bcrypt is unavailable.

Tests cover strict IDs/origins, access lists, legacy owner migration, destination conflicts, symlink rejection, per-user HTTP/upload/SSE/WebSocket routing, forged credentials/cookies, the Supervisor peer gate, blocked calls, capacity, crash recovery, and independent persistent roots with actual gomuks binaries. The network peer is first denied with the production configuration and then simulated on loopback only inside the test.

Real HA acceptance must additionally verify two different Matrix accounts in two encrypted rooms, restart persistence, attachment isolation, allowlist revocation and backup/restore. See [the full checklist](gomuks_web/DOCS.md). Previous single-user E2EE tests do not by themselves validate this multiuser release. No changes are made to MatrixRTC, the Matrix homeserver or your running HA instance by uploading this source.

## Upstream and licensing

The image uses architecture-specific upstream CI tags for gomuks commit `b1ba2099e9d4c0068c7e614d7141b001848369c5`; these are not registry-digest pins. [gomuks](https://github.com/gomuks/gomuks) is AGPL-3.0-or-later. See [third-party notes](THIRD_PARTY.md) before distributing built images. No separate open-source license has yet been selected for this wrapper.
