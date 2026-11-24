# Database backups and point-in-time recovery

How production data is backed up, what we can recover, and who is responsible for it. The step-by-step restore is in [restore-runbook.md](restore-runbook.md); the monthly drill is in [restore-drill.md](restore-drill.md). The job's scripts and an example config are in `infra/backup/`.

Deployment-specific values (storage location, credentials, keys, schedules, retention, monitor names) are deliberately not in this repository. They live in the backup config on the server and in the key holders' offline records. Placeholders such as `<BUCKET>` stand in for them throughout these docs.

## What is protected

- **Databases**: every MariaDB database on the production database server, and the Plane Postgres database.
- **Service configuration**: the configuration the production services need to be rebuilt.
- **Environment files**: the environment files the production services read at start-up.

Application code is not part of the backup: it is rebuilt from this repository.

## How it works

1. **Nightly logical dump.** Each night the job takes a consistent logical dump of every MariaDB database in a single transaction, so it takes no write locks and the site keeps running. The dump records the binary-log file and position it is consistent with, in its header. The Plane Postgres database is dumped on the same run. Service configuration and environment files are archived with it.
2. **Binary-log shipping.** MariaDB writes every change to its binary log. Closed binary-log files are shipped offsite frequently, between nightly dumps. A dump plus the binary logs written after it can rebuild the databases at any moment after the dump.
3. **Client-side encryption.** Everything is compressed and then encrypted on the server with an asymmetric key ([age](https://age-encryption.org/)) before it leaves the machine. The server holds only the public key: it can encrypt new backups but cannot decrypt any of them. Each upload carries a manifest of checksums of its files.
4. **Immutable offsite storage.** Encrypted files go to S3-compatible object storage in a bucket with object lock. A locked object cannot be changed or deleted by anyone, account owners included, until its retention period expires; old objects then age out automatically. The server's storage credential is write-only: it can upload, but not list, read or delete.
5. **Offline restore material.** The credential that can read the bucket and the private key that can decrypt it are kept offline by the key holders. Neither is ever stored on the server, in this repository, or in CI.

A compromised server can therefore stop new backups from being written, but it cannot read, alter or delete the backups already stored.

## Monitoring

Each scheduled part of the job reports a check-in to our error-monitoring service's scheduled-job monitors:

- the nightly backup,
- binary-log shipping,
- disk usage on the backup working area.

A monitor alerts the team on a missed run, a failed run, or a run that takes too long. A disk-usage alert means binary logs or dump staging could fill the disk; deal with it before the next nightly run.

## Recovery capabilities and limits

- **Point in time.** Any MariaDB database can be restored to any moment within the retention window: restore the latest nightly dump before that moment, then replay binary logs up to it.
- **Worst-case data loss** is bounded by the binary-log shipping interval: changes written since the last shipped binary-log file are lost if the server itself is lost. When the server survives, its local binary logs cover that gap.
- **Plane Postgres** is covered by the nightly dump only, so it restores to the last nightly run, not to an arbitrary moment.
- **Retention.** Backups are kept for a short retention window. Anything older has expired and cannot be recovered.
- **Accidental `DROP`, bad `UPDATE` or `DELETE`.** Restore to a separate, isolated instance, replay binary logs to just before the bad statement (by position, found in the binary log), then export the affected tables and load them into production. Production is never restored over directly. See "Recover a dropped table" in the runbook.
- **MariaDB flashback.** For a bad `UPDATE` or `DELETE` (DML only, not `DROP` or other DDL), `mariadb-binlog --flashback` can turn the logged row changes into statements that undo them. It needs row-based binary logging with full row images. Review its output on the side instance before applying anything to production.

## Responsibilities

- **Key holders.** The infrastructure lead role holds the offline restore credential and the private decryption key, with at least one other designated maintainer holding a copy so a restore never depends on one person. Key holders are listed in the team's private records, not here.
- **Monthly restore drill.** A key holder restores a recent point in time on an isolated machine every month and records the result ([restore-drill.md](restore-drill.md)). A backup that has not been restored recently is not trusted.
- **Credential rotation.** Rotate the server's upload credential and the offline restore credential periodically and whenever someone with access leaves. When the encryption key pair is rotated, the server gets the new public key and the old private key is kept offline until every backup encrypted with it has expired.
- **Changes to the job.** Changes to the scripts in `infra/backup/` go through a pull request. Real config values are changed on the server only.
