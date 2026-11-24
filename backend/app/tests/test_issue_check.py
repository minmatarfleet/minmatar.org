"""scripts/check_issue.py, scripts/pr_screenshots.py and the issue forms.

They read the repo checkout, so they skip when only `backend/` is present
(the backend Docker image).
"""

import importlib.util
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "scripts"
FORMS = REPO / ".github" / "ISSUE_TEMPLATE"
HAS_REPO = (SCRIPTS / "check_issue.py").exists() and FORMS.exists()


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"scripts_{name}", SCRIPTS / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def feature(size="Significant: a new page", design="", signed="", box=" "):
    return f"""### Problem

FCs can't see who is late.

### Size

{size}

### Design

{design or "_No response_"}

### Design sign-off

- [{box}] A person decided this ships without a design

### Signed off by

{signed or "_No response_"}
"""


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class IssueCheckTest(unittest.TestCase):
    def setUp(self):
        self.module = _load("check_issue")

    def test_needs_a_type_label(self):
        problems, status = self.module.check("anything", ["backend"])
        self.assertIn("type label", problems[0])
        self.assertEqual(status, {"needs-triage"})
        for label in ("bug", "user-feedback", "security", "tech-debt"):
            self.assertEqual(self.module.check("x", [label]), ([], set()))

    def test_significant_feature_needs_a_design(self):
        problems, status = self.module.check(feature(), ["feature"])
        self.assertEqual(status, {"needs-design"})
        self.assertIn("ask the person", problems[0])
        # A feature written without the form's headings counts as significant.
        self.assertEqual(
            self.module.check("Build it.", ["feature"])[1], {"needs-design"}
        )

    def test_a_design_link_or_a_person_satisfies_it(self):
        linked = feature(design="https://claude.ai/artifact/abc")
        self.assertEqual(self.module.check(linked, ["feature"]), ([], set()))
        signed = feature(box="X", signed="@bearthatcares, same as Fleets tab")
        self.assertEqual(self.module.check(signed, ["feature"]), ([], set()))

    def test_an_agent_cannot_sign_off(self):
        text = feature(box="x", signed="@claude, looks simple")
        problems, status = self.module.check(text, ["feature"])
        self.assertIn("agent or bot", problems[0])
        self.assertEqual(status, {"needs-design"})

    def test_unticked_sign_off_does_not_count(self):
        text = feature(signed="@bearthatcares")
        self.assertEqual(
            self.module.check(text, ["feature"])[1], {"needs-design"}
        )

    def test_small_and_invisible_features_skip_the_design(self):
        for size in (
            "Small: a change inside an existing page",
            "Nothing visible: backend, data or automation only",
        ):
            self.assertEqual(
                self.module.check(feature(size=size), ["feature"]), ([], set())
            )

    def test_github_mode_writes_label_changes(self):
        with tempfile.NamedTemporaryFile("r", delete=False) as out:
            env = {
                "ISSUE_BODY": feature(design="https://claude.ai/artifact/a"),
                "ISSUE_LABELS": json.dumps(["feature", "needs-design"]),
                "GITHUB_OUTPUT": out.name,
            }
            with mock.patch.dict(os.environ, env):
                self.assertEqual(self.module.main(["--github"]), 0)
            written = Path(out.name).read_text(encoding="utf-8")
        os.unlink(out.name)
        self.assertIn("add=\n", written)
        self.assertIn("remove=needs-design\n", written)
        self.assertIn("design_added=false\n", written)


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class IssueFormsTest(unittest.TestCase):
    """The forms write the headings and labels check_issue.py reads."""

    def setUp(self):
        self.module = _load("check_issue")
        self.labels = json.loads(
            (REPO / ".github" / "labels.json").read_text(encoding="utf-8")
        )

    def test_every_type_label_has_a_form_and_each_form_a_type(self):
        types = self.module.type_labels()
        self.assertEqual(
            set(types),
            {"feature", "bug", "user-feedback", "security", "tech-debt"},
        )
        form_labels = set()
        for form in FORMS.glob("*.yml"):
            if form.name == "config.yml":
                continue
            found = re.search(r"^labels:\s*\[(.*)\]", form.read_text(), re.M)
            self.assertIsNotNone(found, form.name)
            form_labels |= set(re.findall(r'"([^"]+)"', found.group(1)))
        self.assertEqual(form_labels, set(types))

    def test_feature_form_headings_match_the_check(self):
        text = (FORMS / "feature.yml").read_text(encoding="utf-8")
        for heading in ("Size", "Design", "Design sign-off", "Signed off by"):
            self.assertRegex(text, rf"(?m)^\s+label: {heading}$")
        for prefix in ("Significant", "Small", "Nothing visible"):
            self.assertIn(f'- "{prefix}:', text)

    def test_labels_are_well_formed(self):
        for label in self.labels:
            self.assertRegex(label["color"], r"^[0-9A-F]{6}$")
            self.assertIn(label["group"], ("type", "status"))
            self.assertLessEqual(len(label["description"]), 100)


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class PullRequestScreenshotsTest(unittest.TestCase):
    def setUp(self):
        self.module = _load("pr_screenshots")

    def test_names_are_url_and_tree_safe(self):
        self.assertEqual(
            self.module.safe_name("feat/fleet tabs"), "feat-fleet-tabs"
        )
        self.assertEqual(self.module.safe_name("../x.png"), "x.png")
        self.assertEqual(self.module.safe_name("///"), "screenshot")

    def test_repo_slug_from_https_and_ssh(self):
        for url in (
            "https://github.com/minmatarfleet/minmatar.org.git",
            "git@github.com:minmatarfleet/minmatar.org.git",
            "https://github.com/minmatarfleet/minmatar.org",
        ):
            self.assertEqual(
                self.module.repo_slug(url), "minmatarfleet/minmatar.org"
            )

    def test_markdown_links_the_raw_file(self):
        lines = self.module.markdown("o/r", "feat-x", ["fleet-390px.png"])
        self.assertEqual(
            lines,
            [
                "![fleet 390px](https://raw.githubusercontent.com/o/r/"
                "pr-screenshots/feat-x/fleet-390px.png)"
            ],
        )
        # The pull request check accepts what the script prints.
        check = _load("check_pull_request")
        self.assertTrue(check.IMAGE.search(lines[0]))
