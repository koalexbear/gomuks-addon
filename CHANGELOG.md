# Changelog

## 0.4.0 — 2026-11-20

**Breaking change: multiuser chat through HA-Ingress only. Back up before migration.**

- Separate gomuks backend, Matrix login, data/keys/cache/logs for each authenticated HA user.
- On-demand startup, optional user admission list, and a configurable running-instance limit.
- Strict owner-only migration of legacy single-user data; no first-visitor assignment.
- Support multiple explicitly allowed Home Assistant HTTPS origins.
- Remove the native desktop listener/configuration and Element Call opt-in. Block the bundled call frontend and keep media permissions denied.
- Replace obsolete single-user/desktop tests with multiuser routing, isolation and migration tests.


## 0.3.0 — 2026-10-27

- Optionaler Desktop-Listener auf internem Port 8098, standardmäßig aus, ohne Host-Portzuordnung.
- Zugriff nur über die beim Start aufgelöste private NPM-Adresse, mit festem HTTPS-Host/Origin.
- Native gomuks-Anmeldung mit eigenem Desktop-Passwort; Ingress-Authentifizierung bleibt getrennt.
- Cookie-Schlüssel bei Änderung der Zugangsdaten erneuern; Desktop-Zugangsdaten bleiben über Neustarts erhalten.
- Integrations-Smoke-Test für echten gomuks-Login und WebSocket hinzugefügt.

## 0.2.0 — 2026-10-27

- Option `enable_calls` (Standard aus) erlaubt Mikrofon/Kamera für das gleich-originige eingebettete Element Call.
- Bildschirmfreigabe bleibt gesperrt; keine weiteren Ports oder API-Rechte.
- Bestehende Installationen ohne die Option bleiben im Chat-Modus.
- Call-Abnahme in HA-Ingress steht noch aus.

## 0.1.1 — 2026-10-25

- Datensparsame HTTP-403-Diagnose für Peer-IP, Benutzer-ID und Origin ergänzt.
- Einrichtung von HA-Origin gegenüber Matrix-Discovery erklärt.
- Manuelle HA-OS-Testergebnisse dokumentiert.

## 0.1.0 — 2026-10-23

- Experimentelles Einzelbenutzer-Add-on mit Ingress, interner Basic-Auth und persistenter Datenablage.
- Initiale Validierungs- und Proxy-Tests sowie E2EE-/Backup-Testanleitung.
