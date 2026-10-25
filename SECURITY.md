# Security and privacy framework

Status: implemented controls for the local synthetic runtime plus requirements for future investor use. The [loopback-runtime report](docs/tasks/T003.4.1-loopback-runtime.md) records host/origin/session checks and resource limits; [import API evidence](docs/tasks/T003.4.2-import-api.md) records the protected import surface. Those scoped results do not establish a current comprehensive security audit, investor installation, encrypted storage, broker credential handling or a public vulnerability intake service. Requirements below remain binding where not yet qualified.

## Data boundary

This project assumes a standard local filesystem source checkout, intended for Git/GitHub version control. Do not place real holdings, brokerage exports, portfolio databases, tax documents, fill confirmations, credentials, portfolio-bearing reports/screenshots or private backups anywhere inside it. This boundary prevents accidental source publication and separates investor state from source/dependency lifecycle. Git ignore rules do not remove files already committed. Ignored `.venv`, tooling caches and synthetic development artifacts may reside inside the checkout.

The future application should choose a per-user local runtime directory outside the source repository and make the choice visible. Review cloud backup, disk protection and access settings with the user at implementation time. A local SQLite file is not automatically encrypted. Do not claim privacy protections that have not been implemented and tested.

Only synthetic portfolios belong in examples, tests, source control, public issues and agent conversations. A real-data task needs explicit authorization defining data, purpose, location and external destinations. Even a developer with local read access must not automatically upload that data to an AI provider, telemetry service or support channel.

The boundary includes UI caches, worker scratch files, exports, traces and research notebooks. Bundle runtime UI resources for offline operation and inventory unexpected network calls. A local launch or synthetic test dataset does not establish that third-party scripts/CDNs/telemetry are absent. Backups must consistently include authoritative referenced evidence and database state; derived caches are separately identified and rebuildable.

## Threats to address during implementation

| Threat | Required design/verification |
| --- | --- |
| Accidental disclosure through logs or source | Synthetic-only development, redacted default diagnostics, secret scanning and opt-in previewable support export |
| Malicious/malformed import | Treat text as data, constrain parsing resources, validate file/schema, safe paths and report escaping |
| Spreadsheet formula injection | Escape dangerous export cell content and verify with adversarial fixtures |
| Local web access abuse | Loopback-only binding by default, origin/request validation, no secrets in URLs |
| Stale/tampered or mistaken financial state | Provenance, explicit reconciliation, immutable plan versions, invalidation and independent validation |
| Concurrent writers/interrupted updates | Transactional commits, locking, migration recovery and tested backup/restore |
| Dependency/update compromise | Pinned/reviewed dependencies, license inventory, identified release artifacts and tested updates |
| Future broker credentials | Scoped access, OS credential storage, revocation; credentials never required for initial file workflow |

## Incident and disclosure handling

No public security contact exists yet. Before public beta, establish a private reporting route and responsible maintainer, document supported versions and response expectations, and test a redacted report workflow. Do not publish account files or credentials in an issue. Never claim an audit, penetration test or review that has not occurred.

For an actual suspected exposure, stop the affected operation, preserve only necessary private evidence, identify the data/destination and involve the owner before external communication. Rotations, deletions and notifications follow explicit authorization and actual incident scope.
