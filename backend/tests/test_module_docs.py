"""Per-module documentation presence guard.

Every module discovered by the loader MUST ship two AI-agent-facing
docs alongside its code:

- ``backend/app/modules/<name>/CLAUDE.md`` — purpose, public API,
  events, permissions, gotchas. Template:
  ``docs/checklists/module-claude-template.md``.
- ``backend/app/modules/<name>/CHANGELOG.md`` — per-module Keep-a-
  Changelog so history is local to the module without `git log`
  archaeology.

If you are adding a new module and this test is failing, you forgot
the docs. Copy the template, fill it, commit. The PR template at
``.github/PULL_REQUEST_TEMPLATE.md`` lists every action a new module
requires.

Both files must be non-trivial (≥ ~10 useful lines). Empty stubs
defeat the purpose; CI rejects them.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from app.core.plugins.loader import discover_modules

MODULES_ROOT = Path(__file__).resolve().parents[1] / "app" / "modules"
SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"

REQUIRED_DOCS = ("CLAUDE.md", "CHANGELOG.md")

# Minimum non-blank lines per doc. Tuned so that a CHANGELOG with just
# `# Title`, `## Unreleased`, one bullet, `## 0.1.0` and a couple of
# bullets passes; an empty stub doesn't. CLAUDE.md is held to a higher
# bar via its dedicated content threshold.
MIN_NON_BLANK_LINES = {"CLAUDE.md": 12, "CHANGELOG.md": 5}


@pytest.fixture(scope="module")
def discovered_module_names() -> list[str]:
    names = sorted(m.name for m in discover_modules())
    assert names, "module discovery returned no modules"
    return names


@pytest.mark.parametrize("doc_name", REQUIRED_DOCS)
def test_every_module_has_doc(discovered_module_names: list[str], doc_name: str) -> None:
    missing: list[str] = []
    too_short: list[tuple[str, int]] = []

    threshold = MIN_NON_BLANK_LINES[doc_name]

    for module_name in discovered_module_names:
        path = MODULES_ROOT / module_name / doc_name
        if not path.exists():
            missing.append(module_name)
            continue
        non_blank = sum(1 for line in path.read_text().splitlines() if line.strip())
        if non_blank < threshold:
            too_short.append((module_name, non_blank))

    assert not missing, (
        f"Modules missing {doc_name}: {missing}. "
        f"Copy docs/checklists/module-claude-template.md and fill it in."
    )
    assert not too_short, (
        f"Modules with sparse {doc_name} (<{threshold} non-blank lines): "
        f"{too_short}. Flesh out the doc — empty stubs defeat the purpose."
    )


# ---------------------------------------------------------------------------
# EN/ES user-manual parity (#128)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def docs_coverage():
    """The check_docs_coverage script, loaded as a module."""
    path = SCRIPTS_ROOT / "check_docs_coverage.py"
    spec = importlib.util.spec_from_file_location("check_docs_coverage", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # dataclasses resolves field types via sys.modules[cls.__module__].
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_locale_parity_flags_one_sided_files(docs_coverage, tmp_path: Path) -> None:
    """A file present in one locale only is an error naming both paths."""
    (tmp_path / "en").mkdir()
    (tmp_path / "es" / "periodontogram" / "screens").mkdir(parents=True)
    (tmp_path / "en" / "demo.md").write_text("# demo\n")
    # Slug translated by mistake — identity broken across locales.
    (tmp_path / "es" / "periodontogram" / "screens" / "periodontograma-view.md").write_text("# v\n")

    findings = docs_coverage.Findings()
    docs_coverage._check_locale_parity(findings, root=tmp_path)

    assert len(findings.errors) == 2
    assert any("en/demo.md" in e and "es/demo.md" in e for e in findings.errors)
    assert any("periodontograma-view.md" in e for e in findings.errors)


def test_locale_parity_passes_on_matching_trees(docs_coverage, tmp_path: Path) -> None:
    for locale in ("en", "es"):
        (tmp_path / locale / "patients" / "screens").mkdir(parents=True)
        (tmp_path / locale / "patients" / "screens" / "list.md").write_text("# list\n")
        (tmp_path / locale / "demo.md").write_text("# demo\n")

    findings = docs_coverage.Findings()
    docs_coverage._check_locale_parity(findings, root=tmp_path)
    assert findings.errors == []


def test_locale_parity_holds_on_the_real_tree(docs_coverage) -> None:
    """The repo's own EN and ES user-manual trees must not drift (#128)."""
    findings = docs_coverage.Findings()
    docs_coverage._check_locale_parity(findings)
    assert findings.errors == [], "\n".join(findings.errors)


# Flow-list frontmatter + strict endpoint normalisation (#543)
# ---------------------------------------------------------------------------


def test_flow_list_parses_to_list_not_string(docs_coverage) -> None:
    """`related_permissions: []` is an empty list, not phantom '[' ']' (#543)."""
    assert docs_coverage._parse_scalar_or_flow_list("[]") == []
    assert docs_coverage._parse_scalar_or_flow_list("['a', 'b']") == ["a", "b"]
    assert docs_coverage._parse_scalar_or_flow_list("patients.read") == "patients.read"


def test_flow_list_in_frontmatter_end_to_end(docs_coverage) -> None:
    """The parsed frontmatter value for `[]` iterates as nothing."""
    fm = docs_coverage._parse_frontmatter("---\nrelated_permissions: []\n---\n# t\n")
    assert fm["related_permissions"] == []
    assert list(fm["related_permissions"]) == []


def test_normalise_strips_example_query_strings(docs_coverage) -> None:
    """Docs may carry `?year=` forms; routes never do (#543)."""
    assert (
        docs_coverage._normalise_endpoint("GET", "/api/v1/payroll/reports/annual?year=")
        == "GET /api/v1/payroll/reports/annual"
    )
