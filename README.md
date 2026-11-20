# gomuks Web for Home Assistant

A single-user Matrix client for Home Assistant OS, with gomuks Web, end-to-end encryption and Home Assistant Ingress. One configured HA user can access one gomuks backend and one Matrix account.

**Experimental.** Chat has been tested on HA OS. Calls and native desktop access need further testing in a real HA/Nginx Proxy Manager setup.

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fkoalexbear%2Fgomuks-addon)

## Features

- HA-Ingress access restricted to an exact HA user ID and the Supervisor's network address.
- No published host ports and no host networking. gomuks listens on container loopback.
- Persistent configuration, messages and encryption keys under `/data/gomuks`.
- Optional microphone/camera permissions for embedded Element Call, disabled by default. An existing MatrixRTC backend is required; screen sharing stays blocked.
- Optional native Linux desktop access through an internal Nginx Proxy Manager connection, disabled by default and protected by separate gomuks credentials.
- Optional Salbei & Stein custom CSS with light/dark palettes and rounded surfaces.

**Matrix encryption keys and decrypted content reside on the HA host.** Trust the host, administrators and backups accordingly. HA-user authentication protects Ingress; desktop credentials independently grant access to the same Matrix account when that route is enabled.

## Install from GitHub

1. In Home Assistant, open **Settings → Apps/Add-ons → App/Add-on Store → ⋮ → Repositories**.
2. Add `https://github.com/koalexbear/gomuks-addon` or use the button above. The repository must be readable by your Supervisor; private GitHub repositories require additional authentication.
3. Install **gomuks Web (private ingress)**. The image is built on your HA device; internet access to the upstream image registry and Alpine repositories is required.
4. Configure the add-on, replacing the example values:

   ```yaml
   allowed_user_id: "0123456789abcdef0123456789abcdef"
   public_origin: "https://ha.example.com"
   enable_calls: false
   desktop:
     enabled: false
     public_origin: ""
     proxy_host: ""
     username: ""
     password: ""
   ```

5. Start the add-on and select **Open Web UI**. Sign in to Matrix and verify the device with a trusted Matrix client.

`allowed_user_id` is the internal ID of your HA user, not a username or Matrix ID. `public_origin` is the exact HTTPS address of **Home Assistant**, including any explicit port, without a path or trailing slash. Do not use the Matrix homeserver URL or its `.well-known` discovery address here.

Never commit actual options, Matrix credentials, tokens, databases or keys. The examples contain placeholders only.

### Updates

For each add-on update, increase `version` in `gomuks_web/config.yaml` and upload the changes to GitHub. Refresh/check for updates in the HA store, then update the existing repository-installed add-on. A GitHub push alone does not update a running container. Back up before updating; do not uninstall to update.

### Moving from a local installation

**The local add-on and the repository-installed add-on have different HA identifiers and separate data directories. Adding this repository does not migrate your current Matrix session, keys or history.**

Before switching, back up the existing local add-on and confirm that you have working Matrix recovery/key backup. Keep the local installation and its data. Stop it, install the repository version, copy the appropriate HA options, and sign in as a new Matrix device. Verify that device and restore the required encryption history before removing anything. Do not run two backends using copies of the same Matrix crypto database.

If you need to preserve the exact existing Matrix device/session, plan a stopped-data migration before switching; this repository does not automate that transfer. Native desktop proxy targets may also need updating because the internal add-on hostname changes.

## Optional calls and desktop access

Set `enable_calls: true` to permit microphone/camera requests by the same-origin embedded Element Call frontend. This does not install RTC services or grant permission through a restrictive parent iframe. First test joining an existing encrypted call on your HA test instance. See the [detailed setup and test guide (German)](gomuks_web/DOCS.md).

For native Linux gomuks, use the [English desktop setup guide](DESKTOP.md). NPM terminates HTTPS and forwards to internal port 8098; no new host-port mapping is needed. Desktop access uses separate credentials, not an HA session. Use only on networks where this is permitted; company/VPN access is not assumed.

## Appearance

Paste [salbei-und-stein.css](themes/salbei-und-stein.css) into gomuks **Custom CSS**. It includes colors, typography, rounded chat panels, message surfaces and larger controls. No rebuild is required. Light/dark mode follows the browser/system preference, not the HA profile automatically. Change `color-scheme: light dark;` to `light` or `dark` to force a mode. See [theme notes (German)](themes/README.md).

## Validation status

- Operator-confirmed on HA OS: image build, HTTPS-Ingress behind NPM, Matrix device verification, encrypted chat, persistence after add-on restart, and denial of a second HA user.
- Locally passed on AMD64: image build, eight Python tests, Ingress proxy regression test, and real-gomuks desktop authentication/cookie/WebSocket smoke test.
- Still pending: full HA restart, update and backup/restore acceptance, actual native Linux/NPM operation, calls through HA-Ingress, and ARM64 acceptance of the desktop route.

These are limited checks, not a claim of production readiness. The detailed documentation records the individual test dates and limitations.

## Development

```sh
python3 -m unittest discover -s tests -v
docker build --build-arg BUILD_ARCH=amd64 -t gomuks-ha:test gomuks_web
docker run --rm --network none --entrypoint python3 \
  -v "$PWD/tests:/tests:ro" gomuks-ha:test /tests/proxy_smoke.py
docker run --rm --network none --entrypoint python3 \
  -v "$PWD/tests:/tests:ro" gomuks-ha:test /tests/desktop_smoke.py
```

The image build needs network access. The smoke tests publish no ports and run without network access. Use `BUILD_ARCH=aarch64` with an appropriate builder for ARM64. You can also install locally by copying `gomuks_web` into `/addons/gomuks_web` and refreshing the store. Rebuild after source changes; restarting alone does not copy new source into the image.

## Upstream and licensing

The image uses architecture-specific upstream gomuks CI tags for commit `b1ba2099e9d4c0068c7e614d7141b001848369c5`; tags are not registry-digest pins. [gomuks](https://github.com/gomuks/gomuks) is licensed under AGPL-3.0-or-later. See [third-party notes](THIRD_PARTY.md) before redistributing built images. No separate open-source license has yet been selected for this wrapper.
