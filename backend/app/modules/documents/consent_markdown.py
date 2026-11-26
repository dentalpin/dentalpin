"""Render a consent body (a small Markdown subset) to sanitised HTML.

This is the only place a consent body becomes markup. The public signing
page and the consent PDF both consume ``render_consent_body`` so what the
patient reads is what gets signed (#1171).

Safety is structural, not a post-hoc scrub:

* markdown-it runs with the ``zero`` preset and only the rules we list in
  ``_ENABLED_RULES``. HTML blocks/inline HTML, links, images, autolinks,
  code, blockquotes, rules, tables and entity decoding are never parsed, so
  their source stays literal text.
* We do not use markdown-it's HTML renderer. ``_render`` walks the token
  stream and emits only the tags in ``ALLOWED_TAGS``. The single attribute is
  ``value="<digits>"`` on an ``li`` inside an ``ol`` (the number the author
  typed, so lists interrupted by a paragraph keep their numbering); it is
  built from ``int()`` and never from raw text. Every text node goes through
  ``html.escape``. A token type the renderer
  does not know degrades to its escaped text.
* Never lose text: markdown-it stops parsing blocks past ``maxNesting`` (20
  token levels, about 10 nested lists), silently dropping the rest of the
  body. ``_loses_text`` detects that and ``render_consent_body`` then falls
  back to the legacy rendering: escaped plain text with ``<br>`` line breaks.

The snapshot kept on the consent stays the *source text*; HTML is derived
on demand. Signed PDFs are stored verbatim with their SHA-256, so changing
this function later never alters evidence that was already signed.
"""

from __future__ import annotations

import re
from html import escape

from markdown_it import MarkdownIt
from markdown_it.token import Token

ALLOWED_TAGS = frozenset({"p", "br", "strong", "em", "h2", "h3", "h4", "ul", "ol", "li"})

# Lines of a legacy plain-text body start with "·", "(1)", "a)" and the like;
# none of those are Markdown syntax, so they stay literal.
_ENABLED_RULES = ["paragraph", "newline", "heading", "list", "emphasis", "escape", "text"]

# "#" -> h2, "##" -> h3, "###" and deeper -> h4. The page and the PDF already
# carry the consent title as the top-level heading.
_HEADING_TAG = {1: "h2", 2: "h3"}

_md = MarkdownIt("zero", {"breaks": True, "html": False, "linkify": False}).enable(_ENABLED_RULES)


# A line that is only list markers ("-", "1.", "- -") has no inline content,
# but it is not lost text.
_MARKER_ONLY = re.compile(r"^\s*(?:[-*]|\d{1,9}[.)])(?:\s+(?:[-*]|\d{1,9}[.)]))*\s*$")


def _heading_tag(token: Token) -> str:
    level = int(token.tag[1:]) if token.tag[:1] == "h" and token.tag[1:].isdigit() else 3
    return _HEADING_TAG.get(level, "h4")


def _render_inline(children: list[Token]) -> str:
    out: list[str] = []
    for child in children:
        kind = child.type
        if kind == "text":
            out.append(escape(child.content))
        elif kind in ("softbreak", "hardbreak"):
            # Single newlines in legacy bodies were visible line breaks.
            out.append("<br>")
        elif kind == "strong_open":
            out.append("<strong>")
        elif kind == "strong_close":
            out.append("</strong>")
        elif kind == "em_open":
            out.append("<em>")
        elif kind == "em_close":
            out.append("</em>")
        else:
            out.append(escape(child.content))
    return "".join(out)


def _render(tokens: list[Token]) -> str:
    out: list[str] = []
    list_kinds: list[str] = []
    for token in tokens:
        kind = token.type
        if kind == "inline":
            out.append(_render_inline(token.children or []))
        elif kind == "heading_open":
            out.append(f"<{_heading_tag(token)}>")
        elif kind == "heading_close":
            out.append(f"</{_heading_tag(token)}>")
        elif kind in ("paragraph_open", "paragraph_close"):
            # Tight list items are rendered without a wrapping paragraph.
            if not token.hidden:
                out.append("<p>" if kind == "paragraph_open" else "</p>")
        elif kind == "bullet_list_open":
            list_kinds.append("ul")
            out.append("<ul>")
        elif kind == "bullet_list_close":
            if list_kinds:
                list_kinds.pop()
            out.append("</ul>")
        elif kind == "ordered_list_open":
            list_kinds.append("ol")
            out.append("<ol>")
        elif kind == "ordered_list_close":
            if list_kinds:
                list_kinds.pop()
            out.append("</ol>")
        elif kind == "list_item_open":
            # markdown-it keeps the typed number in ``info``; keep it so a list
            # split by a paragraph, or one starting at 3, prints what was written.
            number = token.info if list_kinds and list_kinds[-1] == "ol" else ""
            if number.isascii() and number.isdigit():
                out.append(f'<li value="{int(number)}">')
            else:
                out.append("<li>")
        elif kind == "list_item_close":
            out.append("</li>")
        elif token.content:
            out.append(escape(token.content))
    return "".join(out)


def _normalise(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _loses_text(source: str, tokens: list[Token]) -> bool:
    """True when a non-blank source line is not covered by any inline token."""
    covered: set[int] = set()
    for token in tokens:
        if token.type == "inline" and token.map:
            covered.update(range(token.map[0], token.map[1]))
    for number, line in enumerate(source.split("\n")):
        if line.strip() and number not in covered and not _MARKER_ONLY.match(line):
            return True
    return False


def _render_plain(source: str) -> str:
    lines = [escape(line) for line in source.strip("\n").split("\n")]
    return "<p>" + "<br>".join(lines) + "</p>"


def render_consent_body(markdown_text: str | None) -> str:
    """Return sanitised HTML for a consent body.

    Pure and deterministic: the same text always yields the same HTML, and the
    output only contains the tags in ``ALLOWED_TAGS`` (the only attribute is
    ``value`` with digits on ``li`` inside ``ol``). If the parser would drop
    part of the body (lists nested too deep), the whole body is rendered as
    escaped plain text instead: a consent never loses text.
    """
    if not markdown_text or not markdown_text.strip():
        return ""
    source = _normalise(markdown_text)
    tokens = _md.parse(source)
    if _loses_text(source, tokens):
        return _render_plain(source)
    return _render(tokens)


_VALUE_ATTR = re.compile(r'<li value="(\d+)">')


def list_value_css(body_html: str) -> str:
    """CSS that makes WeasyPrint honour ``<li value>`` (it ignores the attribute).

    Browsers honour ``value`` natively. WeasyPrint does not, so the PDF gets one
    ``counter-set`` rule per distinct number. The counter is set before the
    item's own implicit increment, hence ``N - 1``. Only digits from our own
    renderer's output reach the stylesheet.
    """
    numbers = sorted({int(n) for n in _VALUE_ATTR.findall(body_html)})
    return "".join(f'li[value="{n}"]{{counter-set:list-item {n - 1};}}' for n in numbers)
