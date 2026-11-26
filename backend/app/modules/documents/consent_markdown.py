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
  stream and emits only the tags in ``ALLOWED_TAGS``, with no attributes.
  Every text node goes through ``html.escape``. A token type the renderer
  does not know degrades to its escaped text.

The snapshot kept on the consent stays the *source text*; HTML is derived
on demand. Signed PDFs are stored verbatim with their SHA-256, so changing
this function later never alters evidence that was already signed.
"""

from __future__ import annotations

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
            out.append("<ul>")
        elif kind == "bullet_list_close":
            out.append("</ul>")
        elif kind == "ordered_list_open":
            out.append("<ol>")  # the start number is dropped: no attributes are emitted
        elif kind == "ordered_list_close":
            out.append("</ol>")
        elif kind == "list_item_open":
            out.append("<li>")
        elif kind == "list_item_close":
            out.append("</li>")
        elif token.content:
            out.append(escape(token.content))
    return "".join(out)


def render_consent_body(markdown_text: str | None) -> str:
    """Return sanitised HTML for a consent body.

    Pure and deterministic: the same text always yields the same HTML, and the
    output only contains the tags in ``ALLOWED_TAGS``, never an attribute.
    """
    if not markdown_text or not markdown_text.strip():
        return ""
    return _render(_md.parse(markdown_text))
