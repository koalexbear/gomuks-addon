# gomuks Web (private ingress)

Single-user Matrix chat with server-side E2EE, Home Assistant Ingress and an exact HA-user-ID access check. No published host ports.

Set `public_origin` to the HTTPS address of **Home Assistant**, not your Matrix homeserver. Encryption keys and decrypted data reside in the private add-on data directory on the HA host.

Calls and native desktop access are optional and disabled by default. Desktop access uses separate gomuks credentials and is independent of HA login. Read the Documentation tab before enabling either feature.

The [repository README](https://github.com/koalexbear/gomuks-addon#readme) covers installation, updates, migration and the validation status. Existing local installations are separate from repository installations; their data is not migrated automatically.
