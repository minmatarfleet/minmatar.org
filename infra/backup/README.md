# Backup job

Files for the production database backup job. How the backups work and how to restore them is in [docs/operations/backups.md](../../docs/operations/backups.md) and [docs/operations/restore-runbook.md](../../docs/operations/restore-runbook.md).

| File | What it is |
| --- | --- |
| `config.example` | Every setting the job reads, with placeholder values only. |

The job's scripts and scheduling files are added to this folder separately; each is listed here when it is added.

## Real configuration lives only on the server

The filled-in config (storage location, upload credential, encryption public key, monitoring settings) exists only on the production server, readable only by the account that runs the job. `infra/backup/config` and `*.env` are gitignored so a real copy cannot be committed by accident. Schedules, retention and alert thresholds are set on the server too; anything in this folder that looks like one is a placeholder or a marked example.

The restore credential and the private decryption key are never on the server or in this repository.
