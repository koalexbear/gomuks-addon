# gomuks Web (private ingress)

Multiuser Matrix chat: each authenticated HA user gets a separate gomuks backend, Matrix account login, database and encryption-key store. HA-Ingress is the only supported access route; no published host ports.

Configure the exact Home Assistant HTTPS addresses in `public_origins`. Empty `allowed_user_ids` permits all authenticated HA-Ingress users, each with their own instance. `max_instances` limits the number of running backends.

**Before updating from single-user versions, back up the stopped add-on and set `legacy_owner_id` to the existing account owner's HA user ID.** No existing data is assigned to the first visitor. Calls and native desktop access are removed in 0.4.0.

Experimental. Read the Documentation tab for migration, security boundaries and the two-account acceptance test. The [repository README](https://github.com/koalexbear/gomuks-addon#readme) contains installation and development instructions.
