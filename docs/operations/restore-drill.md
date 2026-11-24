# Monthly restore drill

Once a month, a key holder proves the backups can be restored by doing a real point-in-time restore on an isolated machine, following [restore-runbook.md](restore-runbook.md). Nothing touches production.

## Checklist

- [ ] Pick a `<TARGET_TIME>` several days back that falls between two nightly dumps, so the drill exercises both the dump and binary-log replay.
- [ ] Note the start time.
- [ ] Download the dump and binary logs with the offline restore credential.
- [ ] Decrypt with the offline private key and verify every file against its manifest.
- [ ] Start an isolated MariaDB (`--no-defaults`, `--skip-networking`, its own datadir), load the dump and replay binary logs to the target.
- [ ] Restore the Plane Postgres dump into an isolated Postgres.
- [ ] Work through the runbook's validation checklist, including "no rows newer than the target time".
- [ ] Note the end time and the total restore time.
- [ ] Shut both instances down and destroy all decrypted data: downloads, decrypted files, datadirs and exports. Unset the restore credential and return the private key to offline storage.
- [ ] Record the drill in the team's private operations log: date, who ran it, target time, restore time, and any problems.
- [ ] Open an issue or pull request for anything that was wrong or unclear: a step in the runbook, a missing file, a slow step, a monitor that did not alert.

## If the drill fails

Treat a failed drill as an outage of the backups: tell the team, find the cause, and repeat the drill once it is fixed. Do not wait for next month.
