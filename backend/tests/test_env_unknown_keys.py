"""Unknown .env keys are reported, not swallowed (follow-up to #513).

``extra="ignore"`` is required because the root ``.env`` is shared with
docker compose and Nuxt, but it also drops a misspelled app setting in
silence. These tests pin what counts as "foreign and fine" versus "looks
like a typo", and that the shipped templates stay quiet.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from app.config import Settings, unknown_env_keys, warn_unknown_env_keys

DECLARED = set(Settings.model_fields)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_misspelled_setting_is_reported(tmp_path: Path) -> None:
    """The case that motivated this: SENTRY_DNS leaves SENTRY_DSN empty."""
    path = _env(tmp_path, "SENTRY_DNS=https://typo@example.com/1\n")
    assert unknown_env_keys(path, DECLARED) == ["SENTRY_DNS"]


def test_keys_belonging_to_compose_and_nuxt_stay_quiet(tmp_path: Path) -> None:
    path = _env(
        tmp_path,
        "POSTGRES_DB=dental\nPOSTGRES_USER=dental\nAPI_BASE_URL=http://localhost:8000\n"
        "DOCS_URL=https://example.com/docs\n"
        "NUXT_PUBLIC_API_BASE_URL=http://localhost:8000\nSEED_ON_STARTUP=1\n"
        "DENTALPIN_VERSION=1.2.3\nPUBLIC_URL=https://example.com\n",
    )
    assert unknown_env_keys(path, DECLARED) == []


def test_declared_settings_stay_quiet(tmp_path: Path) -> None:
    path = _env(
        tmp_path, "DATABASE_URL=x\nSECRET_KEY=y\nSENTRY_DSN=z\nCOOKIE_DOMAIN=.example.com\n"
    )
    assert unknown_env_keys(path, DECLARED) == []


def test_declared_settings_match_case_insensitively(tmp_path: Path) -> None:
    """pydantic-settings applies ``database_url=`` too, so it is not unknown."""
    path = _env(tmp_path, "database_url=x\nSentry_Dsn=z\n")
    assert unknown_env_keys(path, DECLARED) == []


def test_comments_blanks_and_export_prefixes(tmp_path: Path) -> None:
    path = _env(
        tmp_path, "\n# SENTRY_DNS=commented out\n\nexport SENTRY_DNS=oops\nDATABASE_URL=x\n"
    )
    assert unknown_env_keys(path, DECLARED) == ["SENTRY_DNS"]


def test_a_missing_env_file_is_not_an_error(tmp_path: Path) -> None:
    """The container path: no .env, only variables compose injects."""
    assert unknown_env_keys(tmp_path / "nope.env", DECLARED) == []


def test_the_shipped_templates_would_not_warn() -> None:
    """A clean `cp .env.example .env` must boot without a scary message."""
    for template in (".env.example", ".env.prod.example"):
        path = REPO_ROOT / template
        if not path.is_file():
            continue
        assert unknown_env_keys(path, DECLARED) == [], template


def test_warn_emits_once_and_names_the_key(tmp_path: Path) -> None:
    path = _env(tmp_path, "SENTRY_DNS=oops\n")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warn_unknown_env_keys(path, DECLARED)
    assert len(caught) == 1
    assert "SENTRY_DNS" in str(caught[0].message)
