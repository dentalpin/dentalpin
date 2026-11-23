"""Tests for the ``dentalpin db restore`` CLI command (#1066).

``db backup`` writes the dump with the backend image's ``pg_dump``
(PostgreSQL 17 on the trixie base, archive format 1.16). The ``db``
service's ``pg_restore`` (postgres:15) only reads up to 1.14, so the
restore has to run from the backend image too. ``pg_restore`` is faked
via monkeypatched ``shutil.which`` / ``subprocess.run``, as in
``test_cli_db_backup.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.cli import db as db_cli
from app.cli.__main__ import build_parser, main


class _Settings:
    DATABASE_URL = "postgresql+asyncpg://dental:s3cret@db:5432/dental_clinic"


def _fake_run(calls: list):
    def _run(*a, **k):
        calls.append((a[0], k))
        return subprocess.CompletedProcess(a[0], 0, None, b"")

    return _run


def test_db_restore_subcommand_runs_backend_pg_restore(monkeypatch, tmp_path: Path, capsys) -> None:
    dump = tmp_path / "full_20260907T230000Z.dump"
    dump.write_bytes(b"PGDMP")
    calls: list = []
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/pg_restore")
    monkeypatch.setattr("subprocess.run", _fake_run(calls))
    monkeypatch.setattr("app.cli.db.settings", _Settings())

    code = main(["db", "restore", str(dump)])

    assert code == 0
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv[0] == "pg_restore"
    assert {"--clean", "--if-exists", "--no-owner"} <= set(argv)
    assert argv[-1] == str(dump)
    # Plain libpq DSN, password moved to the environment (never in ps).
    assert "postgresql://dental@db:5432/dental_clinic" in argv
    assert not any("s3cret" in part for part in argv)
    assert kwargs["env"]["PGPASSWORD"] == "s3cret"
    assert "db restore:" in capsys.readouterr().out


def test_db_restore_dash_reads_stdin(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/pg_restore")
    monkeypatch.setattr("subprocess.run", _fake_run(calls))
    monkeypatch.setattr("app.cli.db.settings", _Settings())

    assert main(["db", "restore", "-"]) == 0
    argv, kwargs = calls[0]
    # No filename: pg_restore reads the inherited stdin.
    assert argv[-1] == "postgresql://dental@db:5432/dental_clinic"
    assert "stdin" not in kwargs


def test_restore_database_missing_binary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    error = db_cli.restore_database("postgresql://x", tmp_path / "full.dump")
    assert error is not None and "pg_restore not found" in error


def test_restore_database_missing_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/pg_restore")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _must_not_run())
    error = db_cli.restore_database("postgresql://x", tmp_path / "nope.dump")
    assert error is not None and "dump file not found" in error


def test_cmd_restore_failure_exits_non_zero(monkeypatch, tmp_path: Path, capsys) -> None:
    dump = tmp_path / "full.dump"
    dump.write_bytes(b"PGDMP")
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/pg_restore")
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(
            a[0], 1, None, b"pg_restore: error: unsupported version (1.16) in file header"
        ),
    )
    monkeypatch.setattr("app.cli.db.settings", _Settings())
    args = build_parser().parse_args(["db", "restore", str(dump)])
    assert args.func(args) == 3
    assert "unsupported version" in capsys.readouterr().out


def test_runbooks_restore_with_the_backend_image() -> None:
    """The documented restore must not use the ``db`` service's
    ``pg_restore``: it is older than the backend's ``pg_dump`` and
    cannot read the archive (#1066)."""
    docs = Path(__file__).resolve().parents[2] / "docs"
    for rel in (
        "workflows/backup-restore.md",
        "user-manual/en/operations.md",
        "user-manual/es/operations.md",
    ):
        text = (docs / rel).read_text(encoding="utf-8")
        assert "db pg_restore" not in text, rel
        assert "python -m app.cli db restore" in text, rel


def _must_not_run():
    raise AssertionError("pg_restore must not run when the dump file is missing")
