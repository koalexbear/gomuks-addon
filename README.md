# Home Assistant gomuks Web Add-on

Experimentelles Home-Assistant-OS-Add-on für Matrix-Chat mit gomuks Web, E2EE und Ingress. Eine HA-Benutzer-ID erhält Zugriff auf genau eine gomuks-Instanz mit einem Matrix-Konto.

- Nur Ingress, keine veröffentlichten Host-Ports.
- Zugriff nur vom Supervisor und mit exakt konfigurierter HA-Benutzer-ID.
- gomuks-Backend auf Loopback, interne Basic-Auth bleibt aktiv.
- Persistente Daten und E2EE-Schlüssel im privaten Add-on-Verzeichnis `/data/gomuks`.
- HTTPS erforderlich. `public_origin` ist die Adresse von **Home Assistant**, nicht die Matrix-Homeserver-Adresse.
- Chat als Umfang; keine eingerichteten Call-Ports.

**Die Matrix-E2EE-Schlüssel liegen im Backend auf dem HA-Host.** Host- und HA-Administratoren sowie Backups müssen entsprechend vertrauenswürdig sein.

## Installation

Den Ordner `gomuks_web` nach `/addons/gomuks_web` auf HA OS kopieren. Im Add-on-Store lokale Add-ons neu einlesen, installieren und konfigurieren:

```yaml
allowed_user_id: "0123456789abcdef0123456789abcdef"
public_origin: "https://ha.example.de"
```

Die Beispielwerte ersetzen. `allowed_user_id` ist die interne HA-Benutzer-ID. Origin ohne Pfad oder abschließenden Schrägstrich eintragen. Starten und über „Weboberfläche öffnen“ aufrufen, dann Matrix anmelden und das Gerät verifizieren.

Die vollständige [Einrichtungs- und Testanleitung](gomuks_web/DOCS.md) behandelt E2EE, Persistenz, Backups und Diagnose. Matrix-Passwörter, Tokens, Benutzer-IDs und reale Konfigurationsdateien nicht ins Repository übernehmen.

## Prüfstand

Am 25.10.2026 vom Betreiber auf einer HA-OS-Testinstanz unter Proxmox bestätigt: Build, HTTPS-Ingress über Nginx Proxy Manager, E2EE/Geräteverifizierung, Persistenz nach Add-on-Neustart und Zugriffssperre für einen zweiten HA-Benutzer. HA-Neustart, Updates und Backup/Wiederherstellung stehen noch aus; ARM64 ist noch nicht praktisch abgenommen.

## Entwicklung

```sh
python3 -m unittest discover -s tests -v
docker build --build-arg BUILD_ARCH=amd64 -t gomuks-ha:test gomuks_web
docker run --rm --network none --entrypoint python3 \
  -v "$PWD/tests:/tests:ro" gomuks-ha:test /tests/proxy_smoke.py
```

Der Docker-Test benötigt Docker und Netzwerkzugriff beim Image-Build. Er prüft einen künstlichen Backend-Server und ersetzt keine HA-/E2EE-Abnahme. Für ARM64 `BUILD_ARCH=aarch64` mit passendem Builder verwenden.

## Quellstand und Lizenzhinweise

Das Image verwendet gomuks-CI-Commit-Tags für `b1ba2099e9d4c0068c7e614d7141b001848369c5`. Vor einer Veröffentlichung sollten Image-Digests fixiert werden. [gomuks](https://github.com/gomuks/gomuks) ist AGPL-3.0; siehe [THIRD_PARTY.md](THIRD_PARTY.md). Für den eigenen Wrapper wurde noch keine Open-Source-Lizenz festgelegt.
