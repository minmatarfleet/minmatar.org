"""Turn Google Calendar HTML from NPSI feeds into readable plain text."""

from __future__ import annotations

import html
import re

_DESCRIPTION_MAX_LENGTH = 4000

_BR_RE = re.compile(r"(?i)<br\s*/?>")
_BLOCK_CLOSE_RE = re.compile(r"(?i)</(p|div|h[1-6]|li)>")
_ANCHOR_RE = re.compile(
    r'(?is)<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
)
_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


def sanitize_npsi_description(raw: str | None) -> str:
    if not raw:
        return ""

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _BR_RE.sub("\n", text)
    text = _BLOCK_CLOSE_RE.sub("\n", text)
    text = _ANCHOR_RE.sub(_replace_anchor, text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("**", "")

    lines = [
        _MULTI_SPACE_RE.sub(" ", line).strip() for line in text.split("\n")
    ]
    collapsed: list[str] = []
    pending_blank = False
    for line in lines:
        if not line:
            pending_blank = bool(collapsed)
            continue
        if pending_blank:
            collapsed.append("")
            pending_blank = False
        collapsed.append(line)

    cleaned = _MULTI_BLANK_RE.sub("\n\n", "\n".join(collapsed)).strip()
    return cleaned[:_DESCRIPTION_MAX_LENGTH]


def escape_npsi_description_for_web(text: str | None) -> str:
    """Neutralize HTML for the web schedule sink.

    ``sanitize_npsi_description`` unescapes entities so the Discord embed
    (plain text) reads naturally. The fleet schedule renders the same text
    through ``marked`` + ``set:html`` with no client-side sanitizer, so raw
    ``<``/``>``/``&`` from an untrusted feed would inject live HTML. Escape
    them here, at the boundary into the web-bound copy, so the schedule shows
    the markup as text instead of executing it. Discord keeps the unescaped
    form.
    """
    if not text:
        return ""
    return html.escape(text, quote=False)


def _replace_anchor(match: re.Match[str]) -> str:
    href = html.unescape(match.group(1) or "").strip()
    inner = _TAG_RE.sub("", match.group(2) or "")
    inner = html.unescape(inner).replace("\xa0", " ").strip()
    inner_compact = re.sub(r"\s+", "", inner)
    href_compact = re.sub(r"\s+", "", href)
    if not href:
        return inner
    if not inner_compact or inner_compact == href_compact:
        return href
    if href in inner or inner in href:
        return href
    return f"{inner} ({href})"
