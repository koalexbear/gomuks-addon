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

Die interne gomuks-Basic-Auth bleibt aktiv. Bei jedem Start wird ein neues zufälliges internes Passwort erzeugt; nginx überschreibt eingehende Authorization-Header. Backend-Cookies werden in beide Richtungen unterdrückt, damit alte oder andere gomuks-Sitzungen nicht stören. bcrypt wird dadurch bei Backend-Anfragen wiederholt geprüft: CPU-/Latenzverhalten auf dem Zielgerät testen. Konfiguration/Proxy-Geheimnis werden nicht protokolliert; nginx-Access-Logs sind aus. Upstream-gomuks-Logs können dennoch sensible Metadaten enthalten.

Ingress entfernt den äußeren dynamischen Pfad bereits. nginx gibt den verbleibenden Pfad unverändert weiter. gomuks nutzt `base: "./"`, relative `_gomuks/...`-Aufrufe und einen relativen WebSocket-Endpunkt. Deshalb keine HTML-Ersetzung und kein fest codierter Ingress-Token. Das belegt grundsätzliche Pfadkompatibilität anhand des Quellcodes, ersetzt aber keinen Browser-Test. Die URL muss mit `/` enden. SSO/OIDC-Rücksprünge über einen wechselnden Ingress-Pfad sind gesondert zu testen; zunächst normalen Matrix-Login verwenden, sofern der Homeserver ihn unterstützt.

Chat ist der vorgesehene Umfang. Keine TURN-/UDP-/Call-Ports werden eingerichtet. Die Permissions-Policy sperrt Kamera, Mikrofon und Bildschirmfreigabe; gomuks kann weiterhin Call-Bedienelemente anzeigen. Browser-Push, Widgets, GIF-Suche, Karten, Links und eingebettete Inhalte können zusätzliche externe Zugriffe auslösen und sind nicht Teil der Freigabe. Das Gerüst garantiert keinen vollständig vom Browser getrennten Netzwerkverkehr.

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
