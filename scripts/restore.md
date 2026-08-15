# Phase 1 recovery runbook

Database backups are sensitive operational data and must never be committed. Create one with `./scripts/backup.sh /secure/off-repository/path`, copy it encrypted to separate storage, and test checksums regularly.

To restore into a disposable or explicitly approved target, stop application writes, verify the dump with `sha256sum -c`, take a fresh pre-restore backup, and run:

```bash
docker compose exec -T postgres dropdb -U aegis --if-exists aegis_restore_test
docker compose exec -T postgres createdb -U aegis aegis_restore_test
docker compose exec -T postgres pg_restore -U aegis -d aegis_restore_test --clean --if-exists < /secure/path/aegis-postgres-TIMESTAMP.dump
```

Validate phase/task counts and application migrations against the restore-test database before scheduling any production replacement. Never overwrite the development database without the operator's explicit approval.

Repository recovery is `git clone` of the private GitHub source, checkout of the reviewed tag, generation/recovery of `.env` from an encrypted secret manager, then `docker compose build --pull && docker compose up -d --wait`. `.env` is not in Git; production recovery requires an encrypted, access-controlled secret-store backup. Roll back by deploying the prior immutable image/tag and applying only migrations whose downgrade/data consequences were rehearsed. Redis contains disposable sessions and is rebuilt rather than restored.

Robinhood OAuth tokens and registered-client secrets are deliberately excluded from backup and restore. Restore the isolated gateway image/configuration and encryption-key delivery mechanism, then have the operator reauthorize through the Aegis browser. Never copy gateway ciphertext or its encryption key into repository, database backups, development hosts, CI artifacts, or AI-accessible secret stores.
