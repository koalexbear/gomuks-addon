# gomuks Web für Home Assistant OS

Experimentelles lokales Add-on für **einen HA-Benutzer und ein Matrix-Konto**.
Stand der Prüfung: 23.10.2026. Noch keine Freigabe für den produktiven Betrieb.

## Installation und Konfiguration

1. Den Ordner `gomuks_web` nach `/addons/gomuks_web` auf HA OS kopieren (zum Beispiel über vorhandenen SSH-/Dateizugriff). Unter Einstellungen → Apps/Add-ons → Store die lokalen Apps neu einlesen, dann installieren. Der Build benötigt Internetzugriff auf die gomuks-Registry und Alpine-Pakete.
2. In der Add-on-Konfiguration folgende Werte setzen:

   ```yaml
   allowed_user_id: "0123456789abcdef0123456789abcdef"
   public_origin: "https://ha.example.de"
   ```

   Die ID ist die interne Home-Assistant-Benutzer-ID, **kein** Benutzername und **keine** Matrix-ID. Als Administrator in Einstellungen → Personen → Benutzer den gewünschten Benutzer öffnen und die Benutzer-ID ablesen (ggf. erweiterten Modus einschalten). Falls dort nicht sichtbar: über die authentifizierte HA-WebSocket-API `auth/current_user` beim gewünschten Benutzer dessen `id` ermitteln. Keine `.storage`-Dateien bearbeiten und keine Tokens weitergeben.

   `public_origin` ist exakt die HTTPS-Adresse von Home Assistant, einschließlich eines gegebenenfalls vorhandenen Ports, ohne Pfad oder abschließenden Schrägstrich. Dieses Gerüst unterstützt absichtlich nur einen Origin, keine Wildcards und keine HTTP-URL. Beim Wechsel der HA-Adresse Option anpassen.
3. Starten und „Weboberfläche öffnen“. Mit dem zugelassenen HA-Benutzer anmelden und erst dann das eigene Matrix-Konto in gomuks anmelden. Matrix-Passwort und Recovery-Key gehören nicht in die Add-on-Optionen.
4. Das neue Matrix-Gerät mit einem bestehenden vertrauenswürdigen Client verifizieren. Schlüsselbackup/Recovery gesondert prüfen. Erst danach vertrauliche Chats verwenden.

Es werden keine Host-Ports veröffentlicht, auch keine optional einschaltbaren Portzuordnungen. `8099` ist nur im internen Container-Netz erreichbar und nimmt nur den Supervisor `172.30.32.2` an. gomuks lauscht ausschließlich auf `127.0.0.1:29325` im Container. Kein Host-Netzwerk, Docker-Socket, Supervisor-API-Recht oder zusätzliches Dateisystem-Mapping nötig. Die Sidebar ist keine Zugriffskontrolle; die tatsächliche Benutzerprüfung erfolgt im Proxy für alle Pfade inklusive WebSocket/SSE/Medien.

## Architektur und Grenzen

Browser → HA HTTPS/Ingress → Supervisor → nginx (Peer-IP + exakte Benutzer-ID + Origin-Prüfung) → gomuks auf Loopback → Matrix-Homeserver.

Der Supervisor entfernt eingehende Identitätsheader und setzt seine eigenen. Nur in Verbindung mit der Peer-IP-Prüfung sind diese vertrauenswürdig. Fehlende, falsche, doppelt zusammengeführte oder anders geschriebene IDs erhalten 403. Es gibt keinen Administrator-Bypass. HA-/Host-Administratoren können jedoch grundsätzlich auf Container und Daten zugreifen; sie werden dadurch nicht vom Besitz der Schlüssel ausgeschlossen.

Die interne gomuks-Basic-Auth bleibt aktiv. Ohne Desktop-Zugang wird bei jedem Start ein neues zufälliges internes Passwort erzeugt; bei aktiviertem Desktop-Zugang werden dessen konfigurierte Zugangsdaten verwendet; nginx überschreibt eingehende Authorization-Header. Backend-Cookies werden in beide Richtungen unterdrückt, damit alte oder andere gomuks-Sitzungen nicht stören. bcrypt wird dadurch bei Backend-Anfragen wiederholt geprüft: CPU-/Latenzverhalten auf dem Zielgerät testen. Konfiguration/Proxy-Geheimnis werden nicht protokolliert; nginx-Access-Logs sind aus. Upstream-gomuks-Logs können dennoch sensible Metadaten enthalten.

Ingress entfernt den äußeren dynamischen Pfad bereits. nginx gibt den verbleibenden Pfad unverändert weiter. gomuks nutzt `base: "./"`, relative `_gomuks/...`-Aufrufe und einen relativen WebSocket-Endpunkt. Deshalb keine HTML-Ersetzung und kein fest codierter Ingress-Token. Das belegt grundsätzliche Pfadkompatibilität anhand des Quellcodes, ersetzt aber keinen Browser-Test. Die URL muss mit `/` enden. SSO/OIDC-Rücksprünge über einen wechselnden Ingress-Pfad sind gesondert zu testen; zunächst normalen Matrix-Login verwenden, sofern der Homeserver ihn unterstützt.

Standardmäßig ist nur Chat freigegeben. Keine TURN-/UDP-/Call-Ports werden im Add-on eingerichtet. Ohne `enable_calls` sperrt die Permissions-Policy Kamera, Mikrofon und Bildschirmfreigabe. Mit `enable_calls: true` dürfen ausschließlich gleich-originige eingebettete Inhalte Mikrofon und Kamera anfragen; Bildschirmfreigabe bleibt gesperrt. Extern gehostete Call-Widgets werden durch diese Freigabe nicht unterstützt. Browser-Push, Widgets, GIF-Suche, Karten, Links und eingebettete Inhalte können zusätzliche externe Zugriffe auslösen und sind nicht Teil der Freigabe. Das Gerüst garantiert keinen vollständig vom Browser getrennten Netzwerkverkehr.

**E2EE endet im gomuks-Backend**, nicht im Browser: gomuks entschlüsselt auf dem HA-Host und liefert Inhalte über den geschützten Ingress aus. Das ist weiterhin Matrix-E2EE zwischen den Matrix-Geräten, setzt aber Vertrauen in HA OS, Add-on und Backups voraus. Falls nur der Browser Schlüssel halten darf, passt diese Architektur nicht.

Zugriff vom Firmenrechner/VPN ist ausdrücklich kein vorausgesetzter oder getesteter Anwendungsfall. Zunächst ausschließlich im privaten, erlaubten Netz testen. Nutzung über Firmennetze erst nach Klärung der dortigen Richtlinien.

## Persistenz und Wiederherstellung

`GOMUKS_ROOT=/data/gomuks` hält Konfiguration, Datenbank/Kryptospeicher, Cache und Logs im persistenten privaten Add-on-Datenverzeichnis. Verzeichnisse erhalten 0700, neu erzeugte Dateien durch umask 0077 höchstens 0600. Vorhandene gomuks-Konfigurationsfelder und Token-Schlüssel bleiben beim Start erhalten; die verwalteten Web-Zugriffseinstellungen werden sicher überschrieben. Kein Klartext-Matrix-Passwort wird vom Wrapper gespeichert. `/run` enthält nur flüchtige Proxy-Konfiguration.

Das Verzeichnis enthält Schlüssel, Tokens und gegebenenfalls entschlüsselte Inhalte. Persistenz bedeutet keine zusätzliche Verschlüsselung im laufenden System. HA-Backups mit diesem Add-on einschließen, verschlüsselt sichern und den Backup-Schlüssel getrennt aufbewahren. Für einen konsistenten Testbackup das Add-on stoppen; anschließend wieder starten. Auf einer isolierten Testinstallation wiederherstellen. Original und Wiederherstellung nicht gleichzeitig mit derselben Matrix-Geräteidentität betreiben. Add-on nicht deinstallieren, bevor Backup und Wiederherstellung geprüft sind.

## Automatische Tests

Im Projektverzeichnis:

```sh
python3 -m unittest discover -s tests -v

docker build --build-arg BUILD_ARCH=amd64 -t gomuks-ha:test gomuks_web
docker run --rm --network none --entrypoint python3 \
  -v "$PWD/tests:/tests:ro" gomuks-ha:test /tests/proxy_smoke.py
```

Für ARM64 beim Build `BUILD_ARCH=aarch64` verwenden, auf einem passenden Builder. Keine Ports veröffentlichen. Der Proxy-Test startet einen künstlichen Backend-Server, prüft zunächst die unveränderte Produktionskonfiguration (Loopback und gefälschtes X-Forwarded-For werden abgewiesen) und simuliert danach ausschließlich im Test den Supervisor über Loopback. Er prüft Benutzer-ID, Origin, Cookie-Isolation, Query-/Pfadweitergabe und HTTP-Upgrade. Er prüft weder Matrix-E2EE noch einen vollständigen WebSocket-Datenaustausch.

Der Dockerfile verwendet die upstream-CI-Commit-Tags für AMD64 und ARM64, nicht `latest`. Registry-Verfügbarkeit und Zuordnung zum Quellstand müssen beim erfolgreichen Build bestätigt werden. Vor einer Veröffentlichung zusätzlich Registry-Digests festschreiben, Lizenzen/Quellcode-Angebot für gomuks (AGPL) berücksichtigen und das Image auf Schwachstellen prüfen.

## Abnahme auf Home Assistant OS

- **Zugriff:** Leere/falsche ID verhindert Start bzw. liefert 403. Richtige ID öffnet die UI. Zweiter normaler Benutzer und zweiter Administrator erhalten auch beim direkten Aufruf der Ingress-URL, Medien und WebSocket 403. Anfragen ohne ID werden abgelehnt. Keine Identitätsheader oder Tokens veröffentlichen.
- **Netz:** Keine Portzuordnung in der Add-on-Oberfläche; auf dem HA-Host sind 8099/29325 nicht durch dieses Add-on veröffentlicht. Ein anderer Testcontainer mit gefälschter richtiger Benutzer-ID darf 8099 nicht nutzen. Keine real_ip-/X-Forwarded-For-Vertrauensregel ergänzen.
- **Pfad:** Im Browser-Netzwerkprotokoll bleiben JS/CSS, `_gomuks/auth`, Medien/Uploads und WebSocket unter `/api/hassio_ingress/<token>/`. Keine 404 und keine Requests an HA-root `/_gomuks`. WebSocket liefert 101, Nachrichten kommen live an. Reload, neuer HA-Ingress-Token, Mobilansicht und SSE-Fallback testen. Netzwerkaufzeichnungen enthalten Geheimnisse und dürfen nicht ungefiltert geteilt werden.
- **E2EE:** Neuen verschlüsselten Raum mit einem zweiten vertrauenswürdigen Matrix-Client verwenden. Beidseitig Text und verschlüsselten Anhang senden, Geräteverifizierung und Lesen nach Neustart prüfen. Bestehende Historie mit Recovery/Backup testen. Keine Erfolgsmeldung nur anhand des Schloss-Symbols ableiten.
- **Persistenz:** Matrix-Geräte-ID vor/nach Add-on-Neustart, HA-Neustart und Update bleibt gleich; keine neue Anmeldung nötig, alte und neue Nachrichten entschlüsselbar. Gestopptes Add-on sichern und isoliert wiederherstellen; dieselben Prüfungen wiederholen.
- **Betrieb:** Große Anhänge bis 50 MiB, längere Chat-Sitzung, Verbindungsabbruch, CPU/RAM/Platzverbrauch, sauberes Stoppen und Ausfall eines Kindprozesses testen. Ingress-Logout beendet bestehende WebSocket-Verbindungen möglicherweise nicht sofort; Sitzungsschließung/Entzug am Zielsystem prüfen. Eine neue ID-Konfiguration erfordert Add-on-Neustart und trennt dadurch bestehende Verbindungen.

## Prüfstand (25.10.2026)

Vom Betreiber auf einer HA-OS-Testinstanz unter Proxmox bestätigt: Image-Build und Start, HTTPS-Ingress hinter Nginx Proxy Manager, Matrix-Geräteverifizierung, verschlüsselte Nachrichten, Erhalt von Anmeldung und lesbaren Nachrichten nach Add-on-Neustart sowie 403 für einen zweiten HA-Benutzer. Dies sind manuelle Rückmeldungen, keine automatisierten Ende-zu-Ende-Tests.

Lokal bestanden: vier Python-Tests für Optionsvalidierung, Zugriffskonfiguration und datensparsame Diagnose. Noch offen: kompletter Proxy-Smoke-Test, ARM64-Abnahme, HA-Neustart, Update und Backup/Wiederherstellung. Das Add-on bleibt experimentell.

## Primärquellen

- [gomuks Docker-Installation und Schlüsselablage](https://docs.mau.fi/gomuks/installation.html)
- [gomuks Proxy, Origin und Ein-Konto-Betrieb](https://docs.mau.fi/gomuks/faq.html)
- [HA Ingress: Peer-IP, Identitätsheader, relative Pfade](https://contributors.home-assistant.io/apps/guides/ingress/)
- [HA Add-on-Konfiguration](https://contributors.home-assistant.io/apps/reference/configuration/)
- [Geprüfter gomuks-Quellstand b1ba2099](https://github.com/gomuks/gomuks/tree/b1ba2099e9d4c0068c7e614d7141b001848369c5): Dockerfile.ci, .gitlab-ci.yml, web/vite.config.ts, web/src/App.tsx, web/src/api/client.ts sowie pkg/gomuks/{config,server,gomuks}.go. Der aktuelle Quellstand enthält jüngere Felder als manche gecachten Dokumentationsansichten; die Implementierung richtet sich nach diesem festen Commit.


## Diagnose bei HTTP 403

Die Logzeile `ingress_gate` enthält nur Prüfergebnisse: `peer_ok`, `id_present`, `user_ok`, `origin_ok` und `upstream_status`. Keine Rohwerte von IDs, Origin, Pfaden, Cookies oder Authorization werden in dieser Diagnosezeile ausgegeben. Fehlende ID, abweichender Benutzer oder fremder Origin bleiben gesperrt. `upstream_status=-` bedeutet, dass die Anfrage nicht an gomuks weitergereicht wurde.

Bei `origin_ok=0` den Origin der fehlgeschlagenen Browseranfrage mit `public_origin` vergleichen. Hier gehört die HTTPS-Adresse von **Home Assistant** hinein, nicht die Matrix-Domain aus `.well-known`. Die Zugriffssperren nicht zum Debuggen abschalten.

Dateiänderungen an `rootfs/` erfordern einen Neubau des Add-ons; Änderungen an Optionen nur einen Neustart. Bestehendes Add-on nicht deinstallieren, um Daten zu erhalten.


## Optionale Element Calls ab 0.2.0

Voraussetzung ist ein separat funktionierendes MatrixRTC-Backend, zum Beispiel mit Element/Element X bereits getestet. Das Add-on installiert weder LiveKit noch TURN und verändert keine Homeserver-Konfiguration. Medien laufen im Browser; dessen Netzwerk muss die vom MatrixRTC-Backend verwendeten Dienste erreichen können. Auch bei Calls bleiben `ports: {}`, Loopback-Backend und der HA-Benutzer-ID-Filter unverändert.

### Update und Aktivierung auf der Testinstanz

1. Add-on-Daten vor dem Update sichern. Das bestehende Add-on aktualisieren, nicht deinstallieren.
2. Bei lokaler Installation die geänderten Dateien unter `gomuks_web/` kopieren und neu bauen. Vor allem `config.yaml`, `rootfs/settings.py` und `rootfs/start.py` müssen zusammen aktualisiert werden. Optionale deutsche Beschriftungen liegen in `translations/de.yaml`.
3. Bestehende Optionen beibehalten und `enable_calls: true` ergänzen, dann neu starten. Fehlende Option wird wie `false` behandelt. Browser-Oberfläche vollständig neu laden, damit die neue Permissions-Policy wirksam wird.
4. In gomuks die standardmäßig mitgelieferte Element-Call-Einbettung verwenden. Keine fremde `element_call_base_url` konfigurieren: Mikrofon-/Kamerafreigabe gilt nur für `self`.
5. Zuerst in einem verschlüsselten Testraum einen Call in Element starten und mit gomuks beitreten. Der verwendete gomuks-Commit gibt dem Widget `intent=join_existing` mit; Start neuer Calls und Klingelverhalten getrennt prüfen, nicht voraussetzen.
6. Zunächst Audio in beide Richtungen mit Kopfhörern testen, dann Kamera. Browserfreigaben bewusst erteilen. E2EE-Anzeige und Verhalten des Calls prüfen; verschlüsselter Chat allein bestätigt keine Medien-E2EE.
7. Raumwechsel, Auflegen, Wiederbeitritt und zweites Netzwerk testen. Prüfen, dass ein anderer HA-Benutzer auch die `element-call-embedded`-Ressourcen nicht abrufen kann. Keine Tokens oder Ingress-Links in Diagnosematerial veröffentlichen.
8. `enable_calls: false` setzen, neu starten und komplett neu laden: Mikrofon/Kamera müssen wieder per Policy gesperrt sein, Chat weiterhin funktionieren.

### Grenzen und Diagnose

Die gesamte Berechtigungskette muss passen: äußeres HA-Ingress-iframe, eventuelle Reverse-Proxy-Header, Add-on-Policy, inneres Element-Call-iframe und Browserfreigabe. Das Add-on kann eine Sperre im übergeordneten Dokument nicht aufheben. Bei blockiertem Mikrofon die Firefox-Konsole auf Permissions-Policy/iframe-Meldungen prüfen. Keine HA-Sicherheitsheader pauschal deaktivieren. Bildschirmfreigabe ist in dieser Version nicht freigegeben.

Das HA-Design-CSS erstreckt sich nicht automatisch in das eigene Element-Call-iframe. Ein fremder Teilnehmer kann je nach Call-Auswahl einen anderen RTC-Medienserver bestimmen; reine Erreichbarkeit des eigenen Servers garantiert daher nicht alle föderierten Calls. Firmen-Netz/VPN wird weiterhin nicht vorausgesetzt; dort erst nach Freigabe der zuständigen Richtlinien testen.

Prüfstand 27.10.2026: sechs lokale Python-Tests bestanden, darunter striktes Boolean-Opt-in und unveränderte Zugriffskontrolle in beiden Modi. Neuer Container-Build und echter Call in HA-Ingress noch nicht geprüft. Das aktivierte Feature ist experimentell.


## Optionaler Linux-Desktopzugang ab 0.3.0

### Linux desktop access through Nginx Proxy Manager

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

Tested locally on AMD64: image build, eight Python tests, and real-backend desktop smoke test. Actual Linux GUI/NPM/HA-network operation and ARM64 desktop route still need acceptance on the test instance. Ingress regression smoke-test result is recorded in DOCS.md.

## Sources

- Remote backend: https://docs.mau.fi/gomuks/faq.html
- Exact desktop auth/load flow: https://github.com/gomuks/gomuks/blob/b1ba2099e9d4c0068c7e614d7141b001848369c5/desktop/src/webview.ts


Prüfstand Desktop-Erweiterung: AMD64-Image-Build, acht Python-Tests sowie Desktop-Smoke-Test mit echtem gomuks und bestehender Ingress-Regressions-Smoke-Test erfolgreich. Linux-GUI und tatsächliche NPM/HA-Netzwerkverbindung noch offen.
