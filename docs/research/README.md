# Research notes

This folder holds research write-ups that are safe to publish: market and
player-behaviour studies, crawl reports of UX issues, data notes. The
repository is public, so everything here is public.

## Security findings never go here

Do not commit unfixed security findings to this folder or anywhere else in
the repository. That includes bug-crawl tables, exploit steps, and file and
line references for open vulnerabilities.

- Maintainers: open a draft GitHub security advisory on this repository
  (Security, Advisories, "New draft security advisory"). Drafts are private
  to the maintainers.
- Everyone else: tell a maintainer privately, for example by Discord DM.
- Once a fix has shipped, a short note that names the fixed PR is fine.

`.gitignore` ignores `docs/research/*bug-crawl*` and
`docs/research/*security*` so such notes cannot be committed by accident.
Keep them outside the repository, or force-add them only after the findings
are fixed and the text has been reviewed.

## Each note starts with a status header

Give every note its date, its scope, and which PRs acted on it, so a reader
can tell whether it is still current.
