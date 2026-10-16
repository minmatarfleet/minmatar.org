"""Check a post body against what Reddit's Markdown actually renders.

Blocking problems are syntax Reddit shows as literal text in a self post
(raw HTML, inline images, footnotes, checkbox lists). Warnings are syntax
that renders, but not the way most people expect (single line breaks are
joined, ``` fences don't work on old Reddit, "#word" isn't a heading on new
Reddit).
"""

import re
from dataclasses import dataclass

# Blocking
HTML = "html"
IMAGE = "image"
FOOTNOTE = "footnote"
TASK_LIST = "task_list"
# Warnings
SOFT_LINE_BREAK = "soft_line_break"
FENCED_CODE = "fenced_code"
HEADING_SPACE = "heading_space"

BLOCKING = {HTML, IMAGE, FOOTNOTE, TASK_LIST}

# Enough to point at every kind of problem without flooding the form.
MAX_PROBLEMS = 20
EXCERPT_LENGTH = 40

FENCE_RE = re.compile(r"^ {0,3}(```|~~~)")
INDENTED_CODE_RE = re.compile(r"^(?: {4}|\t)")
INLINE_CODE_RE = re.compile(r"(`+).+?\1")
HTML_RE = re.compile(r"<!--|</?[a-zA-Z][a-zA-Z0-9-]*(?:\s[^<>]*)?/?>")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
FOOTNOTE_RE = re.compile(r"\[\^[^\]\s]+\]")
TASK_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[ xX]\](?:\s|$)")
HEADING_SPACE_RE = re.compile(r"^ {0,3}#{1,6}[^#\s]")
# Lines that start their own block (matched after leading spaces, so nested
# list items count), so a single newline before them is fine.
BLOCK_START_RE = re.compile(
    r"^(?:[-*+]\s|\d+[.)]\s|>|#|\||(?:[-*_]\s*){3,}$|=+\s*$|-+\s*$)"
)


@dataclass(frozen=True)
class MarkdownProblem:
    code: str
    line: int
    excerpt: str

    @property
    def blocking(self) -> bool:
        return self.code in BLOCKING


def _excerpt(text: str) -> str:
    text = text.strip()
    if len(text) <= EXCERPT_LENGTH:
        return text
    return text[: EXCERPT_LENGTH - 1] + "…"


def _strip_inline_code(line: str) -> str:
    return INLINE_CODE_RE.sub("", line)


def _is_plain_text(line: str) -> bool:
    return bool(line.strip()) and not BLOCK_START_RE.match(line.lstrip())


def _is_table_row(line: str) -> bool:
    return "|" in line


def _ends_with_hard_break(line: str) -> bool:
    return line.endswith("  ") or line.rstrip(" ").endswith("\\")


def check_reddit_markdown(text: str) -> list[MarkdownProblem]:
    problems = []
    in_fence = False
    previous = ""
    for number, line in enumerate((text or "").splitlines(), start=1):
        if FENCE_RE.match(line):
            if not in_fence:
                problems.append(MarkdownProblem(FENCED_CODE, number, line))
            in_fence = not in_fence
            previous = ""
            continue
        if in_fence or (INDENTED_CODE_RE.match(line) and not previous):
            previous = ""
            continue

        code_free = _strip_inline_code(line)
        html = HTML_RE.search(code_free)
        if html:
            # One per line: <center>…</center> is one problem, not two.
            problems.append(MarkdownProblem(HTML, number, html.group(0)))
        for match in IMAGE_RE.finditer(code_free):
            problems.append(MarkdownProblem(IMAGE, number, match.group(0)))
        for match in FOOTNOTE_RE.finditer(code_free):
            problems.append(MarkdownProblem(FOOTNOTE, number, match.group(0)))
        if TASK_LIST_RE.match(line):
            problems.append(MarkdownProblem(TASK_LIST, number, line))
        if HEADING_SPACE_RE.match(line):
            problems.append(MarkdownProblem(HEADING_SPACE, number, line))
        if (
            _is_plain_text(previous)
            and _is_plain_text(line)
            and not _ends_with_hard_break(previous)
            and not (_is_table_row(previous) and _is_table_row(line))
        ):
            problems.append(MarkdownProblem(SOFT_LINE_BREAK, number, line))
        previous = line

    problems = [
        MarkdownProblem(p.code, p.line, _excerpt(p.excerpt)) for p in problems
    ]
    # Blocking problems first so a long list of warnings can't hide them.
    problems.sort(key=lambda p: (not p.blocking, p.line))
    return problems[:MAX_PROBLEMS]


def blocking_problems(text: str) -> list[MarkdownProblem]:
    return [p for p in check_reddit_markdown(text) if p.blocking]
