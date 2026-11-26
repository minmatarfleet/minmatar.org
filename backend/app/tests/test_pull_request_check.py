"""scripts/check_pull_request.py: the pull request checklist check.

It reads the repo checkout, so it skips when only `backend/` is present (the
backend Docker image).
"""

import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "check_pull_request.py"
TEMPLATE = REPO / ".github" / "pull_request_template.md"
HAS_REPO = SCRIPT.exists() and TEMPLATE.exists()


def _load():
    spec = importlib.util.spec_from_file_location("check_pull_request", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LIBRARY = """
export const RUST_LIBRARY = {
    'Components/Forms': ['blocks/Button', 'blocks/Input'],
    'EVE': ['blocks/sde/TypeRow'],
} as const
export const OTHER = ['blocks/NotInLibrary']
"""

FRONTEND_RESULT = """Frontend review (frontend-review skill) on abc1234:
- Fixed: raw button replaced with Button
- Open: none
- Checks: npm run test passed, npm run check passed"""

BACKEND_RESULT = """Backend review (backend-review skill) on abc1234:
- Fixed: nothing found
- Open: none
- Checks: tests passed (fleets), black/flake8/pylint clean"""


def _tick(text, phrase):
    return text.replace(f"- [ ] {phrase}", f"- [x] {phrase}", 1)


def _fill(text, section, label, value):
    head, sep, tail = text.partition(f"## {section}")
    return head + sep + tail.replace(f"{label}:", f"{label}: {value}", 1)


def body(issue="Closes #3200", no_issue=False, **reviews):
    """A description from the real template: issue and reviews."""
    text = _reviews_body(**reviews)
    if no_issue:
        text = _tick(text, "No issue for this change")
    text = _fill(text, "Issue", "Issue", issue)
    return text


def _reviews_body(
    frontend="none",
    backend="none",
    rust="none",
    docs="unchanged",
    justification="",
    justified_by="@",
    docs_reason="",
):
    """A description built from the real template, ticked as asked."""
    text = TEMPLATE.read_text(encoding="utf-8")

    def tick(phrase):
        nonlocal text
        text = text.replace(f"- [ ] {phrase}", f"- [x] {phrase}", 1)

    def fill(section, label, value):
        nonlocal text
        head, sep, tail = text.partition(f"## {section}")
        tail = tail.replace(f"{label}:", f"{label}: {value}", 1)
        text = head + sep + tail

    if frontend == "none":
        tick("No website changes")
    elif frontend == "ran":
        tick("Ran the frontend review on the final diff")
        fill("Frontend review", "Result", "\n\n" + FRONTEND_RESULT)
    if backend == "none":
        tick("No backend changes")
    elif backend == "ran":
        tick("Ran the backend review on the final diff")
        fill("Backend review", "Result", "\n\n" + BACKEND_RESULT)
    if rust == "none":
        tick("No shared component or token changed")
    elif rust == "changed":
        tick("This pull request adds or changes a shared component or token")
        fill(
            "Rust component library", "Components / tokens", "Button: new size"
        )
        fill(
            "Rust component library",
            "Human justification",
            "\n\n> " + justification,
        )
        text = text.replace(
            "Justified by: @", f"Justified by: {justified_by}", 1
        )
    if docs == "unchanged":
        tick("No documented behaviour changed")
    elif docs == "updated":
        tick("Updated the docs this change affects")
    elif docs == "both":
        tick("No documented behaviour changed")
        tick("Updated the docs this change affects")
    if docs_reason:
        fill("Documentation", "Docs updated, or why none needed", docs_reason)
    return text


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class PullRequestCheckTest(unittest.TestCase):
    def setUp(self):
        self.module = _load()

    def run_check(self, text, changed, docs=None):
        return self.module.check(text, changed, [LIBRARY], docs or {})

    def test_template_has_every_section_and_box_the_check_reads(self):
        found = self.module.sections(TEMPLATE.read_text(encoding="utf-8"))
        for heading, labels in self.module.LABELS.items():
            self.assertIn(heading, found)
            for label in labels:
                self.assertRegex(found[heading], rf"(?m)^{label}:")
        for phrase in (
            "No website changes",
            "Ran the frontend review on the final diff",
            "No backend changes",
            "Ran the backend review on the final diff",
            "No shared component or token changed",
            "This pull request adds or changes a shared component or token",
            "Updated the docs this change affects",
            "No documented behaviour changed",
            "No issue for this change",
        ):
            self.assertIn(
                f"- [ ] {phrase}", TEMPLATE.read_text(encoding="utf-8")
            )

    def test_empty_template_fails_documentation(self):
        errors, _ = self.run_check(
            TEMPLATE.read_text(encoding="utf-8"), ["README.md"]
        )
        self.assertEqual(len(errors), 2)
        self.assertIn("Issue", errors[0])
        self.assertIn("Documentation", errors[1])

    def test_description_without_the_template_fails(self):
        errors, _ = self.run_check(
            "Fixes the thing.", ["backend/fleets/models.py"]
        )
        self.assertTrue(errors)
        self.assertIn("pull_request_template.md", errors[0])

    def test_frontend_change_needs_the_frontend_review(self):
        changed = ["frontend/app/src/pages/index.astro"]
        errors, _ = self.run_check(body(frontend="none"), changed)
        self.assertTrue(
            any('"No website changes" is ticked' in e for e in errors)
        )
        self.assertTrue(any("frontend-review/SKILL.md" in e for e in errors))
        self.assertEqual(self.run_check(body(frontend="ran"), changed)[0], [])

    def test_review_needs_a_result(self):
        text = (
            body(frontend="none")
            .replace("- [x] No website changes", "- [ ] No website changes")
            .replace(
                "- [ ] Ran the frontend review",
                "- [x] Ran the frontend review",
            )
        )
        errors, _ = self.run_check(
            text, ["frontend/app/rust/stories/x.stories.ts"]
        )
        self.assertEqual(len(errors), 1)
        self.assertIn('"Result:"', errors[0])

    def test_backend_and_bot_changes_need_the_backend_review(self):
        for path in ("backend/fleets/models.py", "bot/main.py"):
            errors, _ = self.run_check(body(backend="none"), [path])
            self.assertTrue(
                any("backend-review/SKILL.md" in e for e in errors)
            )
            self.assertEqual(
                self.run_check(body(backend="ran"), [path])[0], []
            )

    def test_shared_rust_component_needs_a_human_justification(self):
        changed = ["frontend/app/src/components/blocks/Button.astro"]

        errors, _ = self.run_check(body(frontend="ran", rust="none"), changed)
        self.assertTrue(any("Rust" in e and "is ticked" in e for e in errors))

        errors, _ = self.run_check(
            body(frontend="ran", rust="changed"), changed
        )
        self.assertTrue(any("Human justification" in e for e in errors))
        self.assertTrue(any("Justified by" in e for e in errors))

        reason = "Fleet sign-up needs a compact button; every existing size wraps on phones."
        errors, _ = self.run_check(
            body(
                frontend="ran",
                rust="changed",
                justification=reason,
                justified_by="@claude",
            ),
            changed,
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("agent or bot", errors[0])

        errors, _ = self.run_check(
            body(
                frontend="ran",
                rust="changed",
                justification=reason,
                justified_by="@bearthatcares",
            ),
            changed,
        )
        self.assertEqual(errors, [])

    def test_what_counts_as_a_shared_rust_change(self):
        changed = [
            "frontend/app/rust/library.ts",
            "frontend/app/src/components/blocks/sde/TypeRow.astro",
            "frontend/app/src/components/compositions/Grid.astro",
            "frontend/app/src/styles/properties/_colors.scss",
            "frontend/app/src/components/blocks/NotInLibrary.astro",
            "frontend/app/src/components/blocks/fleets/FleetCard.astro",
        ]
        self.assertEqual(
            self.module.rust_changes(changed, [LIBRARY]),
            sorted(changed[:4]),
        )

    def test_library_entries_reads_the_real_library(self):
        text = (REPO / "frontend/app/rust/library.ts").read_text(
            encoding="utf-8"
        )
        entries = self.module.library_entries(text)
        self.assertIn("blocks/Button", entries)
        self.assertIn("compositions/Grid", entries)

    def test_documentation_answer(self):
        errors, _ = self.run_check(body(docs="both"), ["README.md"])
        self.assertIn("exactly one", errors[0])

        errors, _ = self.run_check(body(docs="updated"), ["scripts/thing.py"])
        self.assertIn("no doc is in the diff", errors[0])
        self.assertEqual(
            self.run_check(body(docs="updated"), ["docs/fleets/x.md"])[0], []
        )

    def test_docs_naming_a_changed_file_need_a_reason(self):
        docs = {
            "docs/fleets/overview.md": "Roles come from `fleets/models.py`."
        }
        changed = ["backend/fleets/models.py"]
        errors, notices = self.run_check(body(backend="ran"), changed, docs)
        self.assertEqual(len(errors), 1)
        self.assertIn("docs/fleets/overview.md", errors[0])
        self.assertIn("docs/fleets/overview.md", notices[0])

        text = body(
            backend="ran",
            docs_reason="Only a typo fix; the doc is still right.",
        )
        self.assertEqual(self.run_check(text, changed, docs)[0], [])

        changed_with_doc = changed + ["docs/fleets/overview.md"]
        self.assertEqual(
            self.run_check(
                body(backend="ran", docs="updated"), changed_with_doc, docs
            )[0],
            [],
        )


@unittest.skipUnless(HAS_REPO, "needs the full repository checkout")
class IssueTest(unittest.TestCase):
    def setUp(self):
        self.module = _load()

    def errors(self, text, changed=("scripts/x.py",)):
        return self.module.check(text, list(changed), [LIBRARY], {})[0]

    def test_closes_and_refs_pass(self):
        for line in (
            "Closes #12",
            "fixes #12",
            "Resolves: minmatarfleet/minmatar.org#12",
            "Refs #12",
            "Part of #12",
            "Closes https://github.com/minmatarfleet/minmatar.org/issues/12",
        ):
            self.assertEqual(self.errors(body(issue=line)), [], line)

    def test_missing_or_bare_issue_fails(self):
        errors = self.errors(body(issue=""))
        self.assertEqual(len(errors), 1)
        self.assertIn("Closes #123", errors[0])
        self.assertIn("bare #123", self.errors(body(issue="#12"))[0])

    def test_no_issue_needs_a_reason_and_no_closes(self):
        self.assertIn(
            "say why",
            self.errors(body(issue="", no_issue=True))[0],
        )
        self.assertEqual(
            self.errors(body(issue="Sentry fix from 11-22", no_issue=True)),
            [],
        )
        self.assertIn(
            "closes one",
            self.errors(body(issue="Closes #4", no_issue=True))[0],
        )
