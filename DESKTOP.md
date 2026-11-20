# Linux desktop access through Nginx Proxy Manager

Version 0.3.0 adds an **optional** native-desktop route. It is off by default. This guide assumes NPM is an add-on on the same HA OS host. No host port is mapped: NPM connects to port **8098 on the gomuks add-on's internal hostname**. Port 8099 remains the HA-Ingress route. gomuks itself stays on loopback port 29325.

## Authentication and origins

The native desktop app loads the web frontend from the remote HTTPS address, then supplies username/password at `/_gomuks/auth`. gomuks issues a Secure/HttpOnly session cookie and authenticates subsequent API/WebSocket requests. The initial frontend HTML/static files are available through the NPM route without a login challenge; Matrix data APIs require gomuks authentication. **Do not place a second Basic Auth challenge in front of the whole site:** the tested desktop implementation supplies its credentials only at the gomuks auth endpoint.

Desktop access is independent of the HA login. Anyone with the desktop credentials can access the same Matrix account; the HA-user-ID restriction applies only to the separate Ingress route. Use dedicated random credentials, never HA or Matrix passwords. They are stored in HA add-on options and the password hash in gomuks config; protect HA administrator access and backups. The proxy and backend must be trusted, as must the internal add-on network between NPM and nginx.

Each Linux machine uses the same HTTPS backend address, so this does not require a per-machine browser origin. For LAN use, split DNS can resolve that hostname to HA's local address. Neither HTTP IP URLs nor arbitrary dynamically trusted Host/Origin headers are required. The existing `public_origin` still identifies HA for Ingress; `desktop.public_origin` identifies the separate desktop hostname.

## Prepare on the test instance

1. Back up the existing add-on. Update it to 0.3.0 and rebuild if installed locally. Do not uninstall or copy a second running instance of the Matrix crypto database.
2. Obtain both add-ons' **internal hostnames**, not their UI names. For a local gomuks installation the HA CLI command is `ha addons info local_gomuks_web`; inspect `hostname`. Run `ha addons info <NPM_ADDON_SLUG>` for NPM's hostname. The slug is shown in its HA add-on page URL. Do not share Supervisor tokens or complete session URLs.
3. Keep the existing options, then add:

   ```yaml
   desktop:
     enabled: true
     public_origin: "https://gomuks.example.de"
     proxy_host: "your-npm-addon-hostname"
     username: "desktop"
     password: "REPLACE-WITH-A-NEW-LONG-RANDOM-PASSWORD"
   ```

   Replace the example hostname, address and password before use. Password: at least 20 characters, at most 72 UTF-8 bytes. The NPM hostname is resolved at startup to a private IPv4 address; only that TCP peer is permitted. DNS/validation failure prevents startup. If NPM's internal IP changes, restart gomuks to refresh the allow rule. Stable credentials keep desktop sessions across ordinary restarts; changing username/password or disabling desktop access regenerates the backend cookie-signing key, and the restart terminates existing connections.
4. Start the add-on. Leave `ports: {}` and `host_network: false` unchanged.

## Nginx Proxy Manager

Create a **separate Proxy Host** for `gomuks.example.de`:

- Scheme to upstream: `http`.
- Forward hostname: the **internal gomuks add-on hostname** from step 2.
- Forward port: `8098`.
- Enable WebSocket support.
- Keep normal Host, Authorization and Cookie forwarding; `X-Forwarded-Proto` must be `https` for HTTPS client requests. No forced HA-user-ID header and no rewriting to the HA-Ingress path.
- Select a certificate valid for the desktop hostname, enable Force SSL, and verify the Linux machine trusts it. NPM can manage its own certificate or use a correctly imported certificate/key from your existing Let's Encrypt setup. A certificate for another hostname is not sufficient. The gomuks add-on does **not** need `/ssl` access or a copy of the private key.
- For LAN-only use, configure an IP-based NPM access restriction for the intended LAN and verify access is blocked from outside it. Local DNS alone does not prevent an existing public reverse proxy from serving this hostname. Do not add a site-wide username/password challenge. Credentials still must be required by gomuks for its API.

The desktop listener checks the actual TCP peer, exact configured Host/Origin and `X-Forwarded-Proto: https`. It does not trust X-Forwarded-For to identify NPM. TLS terminates in NPM; the internal HTTP hop remains within the trusted add-on network. Do not expose 8098/29325 through router or host-port mappings.

## Linux client

Install the official gomuks desktop build from https://docs.mau.fi/gomuks/installation.html. In its backend manager add a **remote** backend:

- Address: `https://gomuks.example.de` (no Ingress path, no trailing slash for the tested desktop implementation).
- Username and password: the desktop credentials configured above.
- Display name: for example `Home Assistant`.

Choose the remote profile rather than the default embedded backend. The remote profile should show the existing Matrix account and history without a new Matrix login/device registration. Do not delete existing embedded profiles as part of this test. Use a compatible desktop version: the server/frontend integration was inspected against gomuks commit `b1ba2099e9d4c0068c7e614d7141b001848369c5`.

## Acceptance checks

- Wrong/no desktop password returns 401 from `/_gomuks/auth`; static HTML may still load. A forged HA-user-ID does not grant desktop API access.
- Correct credentials connect the desktop WebSocket and display the existing account/device, history and new messages. Test simultaneously with Ingress, then after add-on restart.
- Ingress remains available only to the selected HA user; another HA user still gets 403.
- Calls still require `enable_calls: true` and browser/client reachability of MatrixRTC. Desktop access does not make RTC available through HA. Test microphone/camera separately; screen sharing remains blocked by the add-on policy.
- Stop/restart NPM and confirm desktop reconnects. If its internal address changed, restart gomuks. Test that direct access from another add-on with a spoofed forwarded address is denied.
- Rotate the desktop password and restart: previous cookie/new login with old password must fail. Disable desktop access: port 8098 must no longer listen while Ingress still works.
- Verify no host port was added and the NPM hostname is reachable only from the networks intended. Company/VPN use requires separate policy approval and is not assumed.

## Automated tests

From the repository root:

```sh
python3 -m unittest discover -s tests -v
docker build --build-arg BUILD_ARCH=amd64 -t gomuks-ha:test gomuks_web
docker run --rm --network none --entrypoint python3 \
  -v "$PWD/tests:/tests:ro" gomuks-ha:test /tests/proxy_smoke.py
docker run --rm --network none --entrypoint python3 \
  -v "$PWD/tests:/tests:ro" gomuks-ha:test /tests/desktop_smoke.py
```

The desktop smoke test starts the actual gomuks binary with temporary data and no Matrix login. It validates the nginx config, denied production peer/forged forwarding, frontend loading without challenge, rejection of missing/wrong credentials, a Secure/HttpOnly cookie, successful authenticated WebSocket upgrade, and denied wrong Origin/Host/plain-HTTP forwarding. After the production peer rejection test, it substitutes loopback for NPM **only inside the test configuration**.

Tested locally on AMD64: image build, eight Python tests, and real-backend desktop smoke test. Actual Linux GUI/NPM/HA-network operation and ARM64 desktop route still need acceptance on the test instance. The existing Ingress regression smoke test also passed.

## Sources

- Remote backend: https://docs.mau.fi/gomuks/faq.html
- Exact desktop auth/load flow: https://github.com/gomuks/gomuks/blob/b1ba2099e9d4c0068c7e614d7141b001848369c5/desktop/src/webview.ts
