"""scripts/issue_claims.py and the issue-claim hooks in agent_hooks.py.

`gh` is never called: the GitHub replies are canned. They read the repo
checkout, so they skip when only `backend/` is present.
"""

import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "scripts"
HAS_REPO = (SCRIPTS / "issue_claims.py").exists()
SLUG = "minmatarfleet/minmatar.org"
NOW = datetime(2026, 11, 24, tzinfo=timezone.utc)


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"scripts_{name}", SCRIPTS / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def reply(
    number=12,
    state="OPEN",
    assignees=(),
    comments=(),
    prs=(),
    typename="Issue",
):
    """A GraphQL reply shaped like fetch_issue's query."""
    return {
        "data": {
            "repository": {
                "issueOrPullRequest": {
                    "__typename": typename,
                    "number": number,
                    "title": "Fleet roster export",
                    "state": state,
                    "url": f"https://github.com/{SLUG}/issues/{number}",
                    "assignees": {"nodes": [{"login": a} for a in assignees]},
                    "comments": {
                        "nodes": [
                            {
                                "author": {"login": login},
                                "createdAt": when.isoformat(),
                                "body": body,
                            }
                            for login, when, body in comments
                        ]
                    },
                    "timelineItems": {
                        "nodes": [
                            {
                                "source": {
                                    "number": n,
                                    "state": s,
                                    "url": f"https://github.com/{SLUG}/pull/{n}",
                                    "author": {"login": author},
                                }
                            }
                            for n, s, author in prs
                        ]
                    },
                }
            }
        }
    }


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class IssueRefsTest(unittest.TestCase):
    def setUp(self):
        self.claims = _load("issue_claims")

    def test_prompt_refs(self):
        text = (
            "Pick up #3193 and issue 3198, see "
            f"https://github.com/{SLUG}/issues/3001 but not "
            "https://github.com/other/repo/issues/5 or a#12 or #1"
        )
        self.assertEqual(
            self.claims.prompt_issues(text, SLUG), [3193, 3198, 3001]
        )

    def test_body_refs_need_a_keyword(self):
        text = "Closes #10\nRefs #11\nMentions #12 in passing"
        self.assertEqual(self.claims.body_issues(text, SLUG), [10, 11])


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class OthersOnItTest(unittest.TestCase):
    def setUp(self):
        self.claims = _load("issue_claims")

    def issue(self, **kwargs):
        return self.claims.parse_issue(reply(**kwargs))

    def test_pull_request_numbers_are_not_issues(self):
        self.assertIsNone(self.issue(typename="PullRequest"))

    def test_assignee_open_pr_and_recent_claim(self):
        issue = self.issue(
            assignees=["alice", "me"],
            prs=[
                (40, "OPEN", "bob"),
                (41, "MERGED", "carol"),
                (42, "OPEN", "me"),
            ],
            comments=[
                ("dave", NOW - timedelta(days=2), "I'm working on this now"),
                ("erin", NOW - timedelta(days=90), "I'll take it"),
                ("frank", NOW, "Same problem here"),
            ],
        )
        reasons = self.claims.others_on_it(issue, "Me", now=NOW)
        self.assertEqual(len(reasons), 3, reasons)
        self.assertIn("assigned to @alice", reasons[0])
        self.assertIn("@bob has open pull request #40", reasons[1])
        self.assertIn("@dave", reasons[2])

    def test_nobody_else(self):
        issue = self.issue(comments=[("me", NOW, "I'm on it")])
        self.assertEqual(self.claims.others_on_it(issue, "me", now=NOW), [])
        self.assertTrue(self.claims.claimed_by(issue, "ME"))
        self.assertFalse(self.claims.claimed_by(self.issue(), "me"))


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class ReportTest(unittest.TestCase):
    def setUp(self):
        self.claims = _load("issue_claims")

    def run_report(self, replies, permission="write", login="me"):
        def gh(repo, *args):  # pylint: disable=unused-argument
            if args[:2] == ("api", "user"):
                return login
            if "permission" in " ".join(args):
                return permission
            number = int(args[-1].split("=")[1])
            found = replies.get(number)
            return json.dumps(found) if found else None

        with mock.patch.object(self.claims, "_gh", side_effect=gh):
            return self.claims.report(REPO, list(replies), SLUG)

    def test_unclaimed_issue_is_assigned_with_access(self):
        found = self.run_report({12: reply()})
        self.assertEqual(found.warnings, [])
        self.assertIn(
            "gh issue edit 12 --add-assignee @me", found.unclaimed[0]
        )

    def test_without_access_comment_instead(self):
        found = self.run_report({12: reply()}, permission="read")
        self.assertIn("gh issue comment 12", found.unclaimed[0])

    def test_someone_else_and_closed(self):
        found = self.run_report(
            {
                12: reply(assignees=["alice"]),
                13: reply(number=13, state="CLOSED"),
            }
        )
        self.assertIn("@alice", found.warnings[0])
        self.assertEqual(len(found.unclaimed), 1)
        self.assertIn("#13 is closed", found.context[0])

    def test_gh_unavailable_reports_nothing(self):
        found = self.run_report({12: reply()}, login="")
        self.assertEqual(
            (found.warnings, found.unclaimed, found.context), ([], [], [])
        )


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class RepoSlugTest(unittest.TestCase):
    def setUp(self):
        self.claims = _load("issue_claims")

    def slug(self, remotes):
        def get_url(args, **kwargs):
            name = args[-1]
            if name not in remotes:
                raise self.claims.subprocess.CalledProcessError(2, args)
            return mock.Mock(stdout=remotes[name] + "\n")

        with mock.patch.object(
            self.claims.subprocess, "run", side_effect=get_url
        ):
            return self.claims.repo_slug(Path("."))

    def test_github_urls(self):
        for url in (
            "https://github.com/minmatarfleet/minmatar.org.git",
            "git@github.com:minmatarfleet/minmatar.org.git",
        ):
            with self.subTest(url=url):
                self.assertEqual(
                    self.slug({"origin": url}), "minmatarfleet/minmatar.org"
                )

    def test_ssh_host_alias(self):
        self.assertEqual(
            self.slug(
                {"origin": "git@github-work:keldar-atm/minmatar.org.git"}
            ),
            "keldar-atm/minmatar.org",
        )

    def test_fork_uses_upstream(self):
        self.assertEqual(
            self.slug(
                {
                    "origin": "git@github-work:keldar-atm/minmatar.org.git",
                    "upstream": "git@github-work:minmatarfleet/minmatar.org.git",
                }
            ),
            "minmatarfleet/minmatar.org",
        )

    def test_no_remote(self):
        self.assertIsNone(self.slug({}))


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class ClaimHooksTest(unittest.TestCase):
    def setUp(self):
        self.hooks = _load("agent_hooks")
        self.claims = self.hooks.issue_claims

    def found(self, warnings=(), unclaimed=()):
        return self.claims.Report(
            warnings=list(warnings), unclaimed=list(unclaimed)
        )

    def test_pr_create_blocks_until_claimed_and_asks_on_conflict(self):
        command = "gh pr create --title x --body 'Closes #12'"
        with mock.patch.object(
            self.claims,
            "report",
            return_value=self.found(
                warnings=["#12 x: assigned to @alice."],
                unclaimed=["#12: `gh issue edit 12 --add-assignee @me`"],
            ),
        ) as report:
            block, ask = self.hooks.claims_gate(command, REPO)
        self.assertEqual(report.call_args.args[1], [12])
        self.assertIn("gh issue edit 12", block)
        self.assertIn("@alice", ask)

    def test_other_commands_are_not_looked_up(self):
        with mock.patch.object(self.claims, "report") as report:
            for command in ("git push", "gh pr edit 5 --body 'Closes #12'"):
                self.assertEqual(
                    self.hooks.claims_gate(command, REPO), (None, None)
                )
        report.assert_not_called()

    def run_main(self, client, event, data, found):
        with mock.patch.object(
            self.hooks, "prompt_report", return_value=found
        ), mock.patch.object(
            self.hooks, "claims_gate", return_value=(None, "Open anyway?")
        ), mock.patch.object(
            self.hooks, "gate", return_value=None
        ), mock.patch(
            "sys.stdin"
        ) as stdin, mock.patch(
            "sys.stdout"
        ) as stdout:
            stdin.read.return_value = json.dumps(data)
            code = self.hooks.main(["agent_hooks.py", client, event])
        out = "".join(c.args[0] for c in stdout.write.call_args_list)
        return code, out

    def test_prompt_warns_the_person_and_tells_the_agent(self):
        found = self.found(
            warnings=["#12 x: assigned to @alice."],
            unclaimed=["#12: `gh issue edit 12 --add-assignee @me`"],
        )
        code, out = self.run_main("claude", "prompt", {"prompt": "#12"}, found)
        reply_ = json.loads(out)
        self.assertEqual(code, 0)
        self.assertIn("@alice", reply_["systemMessage"])
        context = reply_["hookSpecificOutput"]["additionalContext"]
        self.assertIn("ask whether to go ahead", context)
        self.assertIn("gh issue edit 12", context)

        code, out = self.run_main("cursor", "prompt", {"prompt": "#12"}, found)
        self.assertEqual(json.loads(out)["continue"], True)
        self.assertIn("@alice", json.loads(out)["user_message"])

    def test_prompt_without_issues_says_nothing(self):
        code, out = self.run_main(
            "claude", "prompt", {"prompt": "hi"}, self.found()
        )
        self.assertEqual((code, out), (0, ""))

    def test_conflict_asks_the_person(self):
        data = {"tool_input": {"command": "gh pr create --body-file b.md"}}
        _, out = self.run_main("claude", "pre-shell", data, self.found())
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "ask")
        _, out = self.run_main("cursor", "pre-shell", data, self.found())
        self.assertEqual(json.loads(out)["permission"], "ask")
