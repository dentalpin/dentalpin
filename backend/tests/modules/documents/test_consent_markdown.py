"""Unit tests for the consent body renderer (#1171)."""

import re

import pytest

from app.modules.documents.consent_markdown import ALLOWED_TAGS, render_consent_body

TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)([^>]*)>")


def assert_only_allowed_markup(html: str) -> None:
    """Allowlisted tags only; the single attribute is ``value="<digits>"`` on ``li`` in ``ol``."""
    open_lists: list[str] = []
    for closing, name, attrs in TAG.findall(html):
        assert name in ALLOWED_TAGS, f"unexpected tag <{name}> in {html!r}"
        if closing:
            if name in ("ul", "ol"):
                open_lists.pop()
            assert attrs == "", f"unexpected attributes on </{name}> in {html!r}"
            continue
        if name in ("ul", "ol"):
            open_lists.append(name)
        if name == "li" and attrs:
            assert open_lists and open_lists[-1] == "ol", f"value outside <ol> in {html!r}"
            assert re.fullmatch(r' value="\d+"', attrs), f"bad attributes {attrs!r} in {html!r}"
        else:
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


def test_numbered_list_keeps_typed_numbers():
    html = render_consent_body("3. Third\n4. Fourth")
    assert html == '<ol><li value="3">Third</li><li value="4">Fourth</li></ol>'
    assert_only_allowed_markup(html)


def test_numbering_survives_a_paragraph_between_items():
    html = render_consent_body("1. Procedure\n\nWe will extract the tooth.\n\n2. Risks")
    assert 'value="1"' in html and 'value="2"' in html
    assert html == (
        '<ol><li value="1">Procedure</li></ol><p>We will extract the tooth.</p>'
        '<ol><li value="2">Risks</li></ol>'
    )
    assert_only_allowed_markup(html)


def test_lone_numbered_item_keeps_its_number():
    html = render_consent_body("3. Alternatives")
    assert html == '<ol><li value="3">Alternatives</li></ol>'


def test_non_sequential_numbers_are_kept():
    html = render_consent_body("1. a\n2. b\n7. c")
    assert re.findall(r'value="(\d+)"', html) == ["1", "2", "7"]


def test_nested_ordered_list_inside_bullets_and_back():
    html = render_consent_body("- a\n\n  4. x\n  5. y\n- b")
    assert html == (
        '<ul><li><p>a</p><ol><li value="4">x</li><li value="5">y</li></ol></li><li><p>b</p></li></ul>'
    )
    assert_only_allowed_markup(html)


def test_bullet_items_never_get_a_value():
    assert "value" not in render_consent_body("- a\n- b")


def test_deeply_nested_lists_never_lose_text():
    html = render_consent_body("- " * 10 + "x\n\nAFTER")
    assert "AFTER" in html and "x" in html
    assert html == "<p>" + "- " * 10 + "x<br><br>AFTER</p>"
    assert_only_allowed_markup(html)


def test_deep_fallback_escapes_markup():
    html = render_consent_body("- " * 12 + "<b>x</b>\n\nAFTER <i>")
    assert "&lt;b&gt;x&lt;/b&gt;" in html and "AFTER &lt;i&gt;" in html
    assert_only_allowed_markup(html)


def test_moderately_nested_lists_still_render_as_lists():
    html = render_consent_body("- " * 9 + "x\n\nAFTER")
    assert html.count("<ul>") == 9 and "<p>AFTER</p>" in html


def test_empty_list_items_do_not_trigger_the_fallback():
    assert render_consent_body("-\n- a") == "<ul><li></li><li>a</li></ul>"


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


def test_list_value_css_only_contains_digits_from_rendered_values():
    from app.modules.documents.consent_markdown import list_value_css

    css = list_value_css(render_consent_body("1. a\n\nx\n\n2. b\n\n3. c"))
    assert css == (
        'li[value="1"]{counter-set:list-item 0;}li[value="2"]{counter-set:list-item 1;}'
        'li[value="3"]{counter-set:list-item 2;}'
    )
    assert list_value_css(render_consent_body('- a\n\n<li value="9">')) == ""
