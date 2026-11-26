"""Unit tests for the consent body renderer (#1171)."""

import re

import pytest

from app.modules.documents.consent_markdown import ALLOWED_TAGS, render_consent_body

TAG = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)([^>]*)>")


def assert_only_allowed_markup(html: str) -> None:
    for name, attrs in TAG.findall(html):
        assert name in ALLOWED_TAGS, f"unexpected tag <{name}> in {html!r}"
        assert attrs == "", f"unexpected attributes on <{name}> in {html!r}"


def test_empty_body_renders_nothing():
    assert render_consent_body("") == ""
    assert render_consent_body("  \n ") == ""
    assert render_consent_body(None) == ""


def test_plain_text_keeps_single_newlines_as_line_breaks():
    # Legacy bodies are plain text with single newlines; each one was a visible line.
    assert render_consent_body("Line one\nLine two\nLine three") == (
        "<p>Line one<br>Line two<br>Line three</p>"
    )


def test_blank_line_separates_paragraphs():
    assert render_consent_body("First\nstill first\n\nSecond") == (
        "<p>First<br>still first</p><p>Second</p>"
    )


def test_crlf_is_normalised():
    assert render_consent_body("a\r\nb\r\n\r\nc") == "<p>a<br>b</p><p>c</p>"


def test_headings_map_to_h2_h4():
    html = render_consent_body("# One\n## Two\n### Three\n#### Four\n###### Six")
    assert html == "<h2>One</h2><h3>Two</h3><h4>Three</h4><h4>Four</h4><h4>Six</h4>"


def test_hash_without_space_is_literal():
    assert render_consent_body("#hashtag") == "<p>#hashtag</p>"


def test_bold_and_italic():
    assert render_consent_body("a **bold** and *italic* and ***both***") == (
        "<p>a <strong>bold</strong> and <em>italic</em> and <em><strong>both</strong></em></p>"
    )


def test_unbalanced_markers_stay_literal():
    assert render_consent_body("2 * 3 = 6 and **open") == "<p>2 * 3 = 6 and **open</p>"


@pytest.mark.parametrize("marker", ["-", "*"])
def test_bullet_lists(marker):
    html = render_consent_body(f"Risks:\n\n{marker} Pain\n{marker} Swelling")
    assert html == "<p>Risks:</p><ul><li>Pain</li><li>Swelling</li></ul>"


def test_numbered_list_drops_start_attribute():
    html = render_consent_body("3. Third\n4. Fourth")
    assert html == "<ol><li>Third</li><li>Fourth</li></ol>"


def test_nested_list_and_inline_markup_inside_items():
    html = render_consent_body("- **a**\n  - nested\n- b")
    assert html == "<ul><li><strong>a</strong><ul><li>nested</li></ul></li><li>b</li></ul>"


def test_bullet_character_lines_stay_literal_text():
    assert render_consent_body("· first\n· second") == "<p>· first<br>· second</p>"
    assert render_consent_body("(1) first\n(2) second") == "<p>(1) first<br>(2) second</p>"


def test_html_is_escaped_not_passed_through():
    html = render_consent_body('<script>alert("x")</script>\n\n<img src=x onerror=alert(1)>')
    assert "<script" not in html and "<img" not in html
    assert "&lt;script&gt;" in html and "&lt;img src=x onerror=alert(1)&gt;" in html
    assert_only_allowed_markup(html)


def test_html_comments_blocks_and_entities_stay_text():
    html = render_consent_body("<!-- c -->\n\n<div>x</div>\n\n&lt;b&gt; &amp; &#60;")
    assert "<div" not in html and "<!--" not in html
    assert "&amp;lt;b&amp;gt; &amp;amp; &amp;#60;" in html
    assert_only_allowed_markup(html)


def test_markup_inside_formatting_is_escaped():
    html = render_consent_body("**<b onclick=x>bold</b>** # <i>")
    assert html == "<p><strong>&lt;b onclick=x&gt;bold&lt;/b&gt;</strong> # &lt;i&gt;</p>"


@pytest.mark.parametrize(
    "source",
    [
        "[click](javascript:alert(1))",
        "![img](https://example.invalid/x.png)",
        "<https://example.invalid>",
        "https://example.invalid/auto",
        "`code`",
        "```\nfenced\n```",
        "> quote",
        "---",
        "***",
        "| a | b |\n|---|---|\n| 1 | 2 |",
        "[ref]: https://example.invalid\n\n[ref]",
    ],
)
def test_unsupported_syntax_stays_literal_text(source):
    html = render_consent_body(source)
    assert_only_allowed_markup(html)
    assert "href" not in html and "src=" not in html
    # Every visible character of the source survives, escaped.
    visible = re.sub(r"<[^>]+>", "", html)
    for chunk in re.split(r"\s+", source):
        assert chunk.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") in visible


def test_setext_underline_and_indented_code_are_not_special():
    assert render_consent_body("Title\n=====") == "<p>Title<br>=====</p>"
    assert render_consent_body("    indented") == "<p>indented</p>"


def test_backslash_escapes_a_marker():
    assert render_consent_body(r"\*not italic\* and C:\Users") == (
        "<p>*not italic* and C:\\Users</p>"
    )


def test_quotes_and_unicode_are_preserved():
    assert render_consent_body('He said "ok" & left — ñ 日本') == (
        "<p>He said &quot;ok&quot; &amp; left — ñ 日本</p>"
    )


def test_rendering_is_deterministic():
    source = "# T\n\nA **b**\nc\n\n- x\n- y\n\n1. z"
    assert render_consent_body(source) == render_consent_body(source)


def test_output_only_uses_allowlisted_tags_for_a_mixed_document():
    html = render_consent_body(
        "# T\n\n<script>x</script> **b** *i*\nbreak\n\n- a\n- b\n\n1. c\n2. d\n\n[l](http://x)"
    )
    assert_only_allowed_markup(html)
