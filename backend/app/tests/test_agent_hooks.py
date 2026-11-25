"""scripts/agent_hooks.py and scripts/ci_local.py: the agent CI hooks.

They read the repo checkout, so they skip when only `backend/` is present
(the backend Docker image).
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "scripts"
HAS_REPO = (SCRIPTS / "agent_hooks.py").exists()


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"scripts_{name}", SCRIPTS / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    # dataclasses look the module up in sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HEREDOC_CREATE = """gh pr create --title "Fix it" --body "$(cat <<'EOF'
## Summary
Runs git push in the docs.
EOF
)\""""


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class PullRequestBodyTest(unittest.TestCase):
    def setUp(self):
        self.hooks = _load("agent_hooks")
        self.cwd = Path(tempfile.mkdtemp())

    def test_heredoc_body(self):
        body, _ = self.hooks.pr_body(HEREDOC_CREATE, self.cwd)
        self.assertEqual(body, "## Summary\nRuns git push in the docs.")

    def test_body_file(self):
        (self.cwd / "body.md").write_text("from file")
        body, _ = self.hooks.pr_body(
            "gh pr create --title x --body-file body.md", self.cwd
        )
        self.assertEqual(body, "from file")

    def test_body_file_written_by_the_same_command(self):
        (self.cwd / "body.md").write_text("stale")
        command = (
            "cat > body.md <<'EOF'\nfresh\nEOF\n"
            "gh pr create --title x --body-file body.md"
        )
        body, _ = self.hooks.pr_body(command, self.cwd)
        self.assertEqual(body, "fresh")

    def test_literal_body(self):
        body, _ = self.hooks.pr_body(
            "gh pr create -t x --body 'short text'", self.cwd
        )
        self.assertEqual(body, "short text")

    def test_shell_built_body_is_not_guessed(self):
        body, why = self.hooks.pr_body(
            'gh pr create -t x --body "$BODY"', self.cwd
        )
        self.assertIsNone(body)
        self.assertIn("shell", why)

    def test_no_body(self):
        body, _ = self.hooks.pr_body("gh pr create --fill", self.cwd)
        self.assertIsNone(body)


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class GateTest(unittest.TestCase):
    def setUp(self):
        self.hooks = _load("agent_hooks")
        self.ci = mock.patch.object(
            self.hooks, "_ci", return_value=(False, "FAIL backend-tests")
        )
        self.body = mock.patch.object(
            self.hooks, "_check_body", return_value=(True, "")
        )
        self.ci_mock = self.ci.start()
        self.body_mock = self.body.start()
        self.addCleanup(mock.patch.stopall)

    def gate(self, command):
        return self.hooks.gate(command, REPO)

    def test_ordinary_commands_pass_without_checks(self):
        for command in (
            "git status",
            "git commit -m 'git push later'",
            "echo gh pr create",
            "gh pr view 12",
            "gh pr edit 12 --add-label bug",
        ):
            self.assertIsNone(self.gate(command), command)
        self.ci_mock.assert_not_called()

    def test_push_runs_ci_and_blocks_on_failure(self):
        reason = self.gate("cd backend && git push -u origin HEAD")
        self.assertIn("FAIL backend-tests", reason)
        self.ci_mock.assert_called_once()

    def test_deleting_a_branch_is_not_gated(self):
        self.assertIsNone(self.gate("git push origin --delete old-branch"))
        self.assertIsNone(self.gate("git push origin :old-branch"))

    def test_skip_marker(self):
        self.assertIsNone(self.gate("CI_LOCAL_SKIP=1 git push"))

    def test_heredoc_text_is_not_a_command(self):
        command = HEREDOC_CREATE.replace("gh pr create", "gh pr edit 5")
        self.ci_mock.return_value = (True, "")
        mock.patch.object(self.hooks, "_is_draft", return_value=False).start()
        self.assertIsNone(self.gate(command))
        self.ci_mock.assert_not_called()
        self.body_mock.assert_called_once()

    def test_create_checks_body_and_ci_once(self):
        self.ci_mock.return_value = (True, "")
        self.body_mock.return_value = (False, "- Frontend review missing")
        reason = self.gate("git push -u origin HEAD && " + HEREDOC_CREATE)
        self.assertIn("Frontend review missing", reason)
        self.ci_mock.assert_called_once()

    def test_each_filtered_hook_checks_only_its_kind(self):
        command = "git push -u origin HEAD && " + HEREDOC_CREATE
        self.body_mock.return_value = (False, "- Frontend review missing")
        push = self.hooks.gate(command, REPO, "push")
        self.assertIn("FAIL backend-tests", push)
        self.assertNotIn("Frontend review", push)
        self.ci_mock.reset_mock()
        pr = self.hooks.gate(command, REPO, "pr")
        self.assertIn("Frontend review missing", pr)
        self.ci_mock.assert_not_called()
        self.assertIsNone(self.hooks.gate(command, REPO, "issue"))

    def test_create_checks_only_the_body(self):
        self.assertIsNone(self.gate(HEREDOC_CREATE))
        self.ci_mock.assert_not_called()
        self.body_mock.assert_called_once()

    def test_create_without_a_readable_body_is_blocked(self):
        self.ci_mock.return_value = (True, "")
        self.assertIn("--body-file", self.gate("gh pr create --fill"))

    def test_editing_a_draft_skips_the_body(self):
        with mock.patch.object(self.hooks, "_is_draft", return_value=True):
            self.assertIsNone(self.gate("gh pr edit 5 --body 'wip'"))
        self.body_mock.assert_not_called()

    def test_ready_undo_is_not_gated(self):
        self.assertIsNone(self.gate("gh pr ready 5 --undo"))
        self.ci_mock.assert_not_called()

    def test_issue_create_needs_a_type_label(self):
        reason = self.gate("gh issue create -t 'Thing' --body 'Fix the thing'")
        self.assertIn("type label", reason)
        self.ci_mock.assert_not_called()
        self.assertIsNone(
            self.gate("gh issue create -t 'Thing' -l bug --body 'Broken'")
        )

    def test_issue_create_significant_feature_needs_a_design(self):
        reason = self.gate(
            "gh issue create -t 'New page' --label feature --body 'Build it'"
        )
        self.assertIn("design", reason)
        body = "### Size\n\nSmall: a change inside an existing page"
        command = (
            "gh issue create -t x --label 'feature,user-feedback' "
            f"--body \"$(cat <<'EOF'\n{body}\nEOF\n)\""
        )
        self.assertIsNone(self.gate(command))

    def test_issue_create_in_the_browser_is_not_gated(self):
        self.assertIsNone(self.gate("gh issue create --web"))

    def test_issue_labels(self):
        self.assertEqual(
            self.hooks.issue_labels(
                'gh issue create -l bug --label "feature, user-feedback"'
            ),
            ["bug", "feature", "user-feedback"],
        )

    def test_draft_skips_the_body(self):
        self.ci_mock.return_value = (True, "")
        self.assertIsNone(self.gate("gh pr create --draft --fill"))
        self.body_mock.assert_not_called()


class ClientOutputTest(unittest.TestCase):
    def run_main(self, client, event, data):
        hooks = _load("agent_hooks")
        with mock.patch.object(
            hooks, "gate", return_value="blocked because"
        ), mock.patch("sys.stdin") as stdin, mock.patch(
            "sys.stdout"
        ) as stdout, mock.patch(
            "sys.stderr"
        ) as stderr:
            stdin.read.return_value = json.dumps(data)
            code = hooks.main(["agent_hooks.py", client, event])
        out = "".join(c.args[0] for c in stdout.write.call_args_list)
        err = "".join(c.args[0] for c in stderr.write.call_args_list)
        return code, out, err

    def test_claude_blocks_with_exit_2(self):
        code, _, err = self.run_main(
            "claude", "pre-shell", {"tool_input": {"command": "git push"}}
        )
        self.assertEqual(code, 2)
        self.assertIn("blocked because", err)

    def test_cursor_denies_with_json(self):
        code, out, _ = self.run_main(
            "cursor", "pre-shell", {"command": "git push"}
        )
        self.assertEqual(code, 0)
        reply = json.loads(out)
        self.assertEqual(reply["permission"], "deny")
        self.assertIn("blocked because", reply["agent_message"])


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class CiLocalPlanTest(unittest.TestCase):
    def setUp(self):
        self.ci = _load("ci_local")

    def names(self, changed):
        return [c.name for c in self.ci.plan(changed, False, False, {})]

    def test_checks_follow_the_changed_paths(self):
        self.assertEqual(
            self.names(["backend/fleets/models.py"]),
            ["backend-lint", "backend-tests"],
        )
        self.assertEqual(
            self.names(["frontend/app/src/pages/index.astro"]),
            ["frontend-tests", "frontend-types"],
        )
        self.assertEqual(
            self.names(["desktop/src/main/api.js"]),
            [
                "backend-tests",
                "desktop",
            ],
        )
        self.assertEqual(self.names(["bot/main.py"]), ["bot"])
        self.assertEqual(
            self.names([".claude/rules/testing.md"]),
            ["agent-config", "backend-tests"],
        )

    def test_docs_run_only_the_app_tests(self):
        (check,) = self.ci.plan(["docs/README.md"], False, False, {})
        self.assertIn("app.tests", check.steps[-1])

    def test_migrations_add_the_migration_tests(self):
        (tests,) = self.ci.plan(
            ["backend/fleets/migrations/0099_x.py"], False, False, {}
        )
        self.assertIn("migration", tests.steps[-1])
        self.assertIn("--tag", tests.steps[-1])

    def test_unrelated_changes_run_nothing(self):
        self.assertEqual(self.names(["mobile/App.tsx"]), [])

    def backend_step(self, changed, **kwargs):
        checks = self.ci.plan(changed, False, False, {}, **kwargs)
        (tests,) = [c for c in checks if c.name == "backend-tests"]
        return tests, next(s for s in tests.steps if "--parallel" in s)

    def test_an_app_change_tests_that_app_and_its_importers(self):
        tests, step = self.backend_step(["backend/moons/models.py"])
        self.assertIn("moons", step)
        self.assertIn("app", step)
        self.assertNotIn("fleets", step)
        self.assertTrue(tests.cache_key.startswith("backend-tests:"))

    def test_a_module_is_matched_not_its_whole_app(self):
        apps = self.ci.affected_backend_apps(["backend/eveonline/scopes.py"])
        self.assertIn("tribes", apps)  # tribes imports eveonline.scopes
        self.assertNotIn("moons", apps)

    def test_shared_files_and_the_flag_run_the_whole_suite(self):
        for changed, kwargs in (
            (["backend/app/settings_test.py"], {}),
            (["backend/Pipfile.lock"], {}),
            (["backend/moons/models.py"], {"full_backend": True}),
        ):
            tests, step = self.backend_step(changed, **kwargs)
            self.assertEqual("--exclude-tag", step[-2])
            self.assertEqual("backend-tests", tests.cache_key)

    def test_tests_run_on_a_copy_of_the_template(self):
        tests, _ = self.backend_step(["backend/moons/models.py"])
        self.assertIn(
            ["cp", self.ci.TEMPLATE_DB, self.ci.TEST_DB], tests.steps
        )
        # The parallel clones from the last run are removed first.
        self.assertLess(
            tests.steps.index(["rm", "-rf", ".test-db/run"]),
            tests.steps.index(["cp", self.ci.TEMPLATE_DB, self.ci.TEST_DB]),
        )
        self.assertEqual(self.ci.TEST_DB, tests.env["TEST_DB_NAME"])
        self.assertNotEqual(self.ci.TEMPLATE_DB, self.ci.TEST_DB)

    def test_text_only_website_changes_skip_the_type_check(self):
        with mock.patch.object(
            self.ci, "removed_translation_keys", return_value=[]
        ):
            self.assertEqual(
                self.names(["frontend/app/src/i18n/ui.ts"]),
                ["frontend-tests"],
            )
            self.assertNotIn(
                "frontend-types", self.names(["frontend/app/README.md"])
            )
        with mock.patch.object(
            self.ci, "removed_translation_keys", return_value=["gone"]
        ):
            self.assertIn(
                "frontend-types", self.names(["frontend/app/src/i18n/ui.ts"])
            )


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class CursorHooksTest(unittest.TestCase):
    def test_every_claude_hook_has_a_cursor_event(self):
        sync = _load("sync_agent_config")
        settings = (REPO / ".claude" / "settings.json").read_text()
        cursor = json.loads(sync.render_hooks(settings))
        self.assertEqual(
            set(cursor["hooks"]),
            {"beforeShellExecution", "postToolUse", "beforeSubmitPrompt"},
        )
        for entries in cursor["hooks"].values():
            for entry in entries:
                self.assertIn(" cursor ", entry["command"])
                self.assertNotIn("CLAUDE_PROJECT_DIR", entry["command"])
        # The kinds Claude filters with `if` are one unfiltered Cursor hook.
        self.assertEqual(
            cursor["hooks"]["beforeShellExecution"],
            [
                {
                    "command": "python3 scripts/agent_hooks.py cursor pre-shell",
                    "timeout": 1800,
                }
            ],
        )

    def test_claude_shell_hooks_are_filtered(self):
        settings = json.loads((REPO / ".claude" / "settings.json").read_text())
        (group,) = settings["hooks"]["PreToolUse"]
        for hook in group["hooks"]:
            self.assertTrue(hook["if"].startswith("Bash("), hook)
            self.assertIn(
                hook["command"].rsplit(" ", 1)[1], ("push", "pr", "issue")
            )


PARALLEL_FAILURE = """Preserving test database for alias 'default'...
noise from a signal

test_x (fleets.tests.test_views.FleetTest) failed:

    AssertionError('1 != 2')

Unfortunately, tracebacks cannot be pickled, making it impossible for the
parallel test runner to handle this exception cleanly.
Ran 10 tests in 1.0s
FAILED (failures=1)
"""


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class DjangoExcerptTest(unittest.TestCase):
    def test_parallel_failure_shows_the_test_not_the_noise(self):
        excerpt = _load("ci_local").django_excerpt(PARALLEL_FAILURE)
        self.assertIn("FleetTest) failed:", excerpt)
        self.assertIn("1 != 2", excerpt)
        self.assertIn("FAILED (failures=1)", excerpt)
        self.assertNotIn("noise from a signal", excerpt)
        self.assertNotIn("Unfortunately", excerpt)
