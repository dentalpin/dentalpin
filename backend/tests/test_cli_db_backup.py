"""Tests for the ``dentalpin db backup`` CLI command.

The pg_dump/storage helpers are pure filesystem + subprocess calls, so
they run without a database: ``pg_dump`` is faked via monkeypatched
``shutil.which`` / ``subprocess.run``, storage roots are ``tmp_path``.
"""

from __future__ import annotations

import argparse
import subprocess
import tarfile
from pathlib import Path

from app.cli import db as db_cli


def _args(**overrides):
    base = {"out_dir": None, "keep": 7, "skip_storage": False}
    base.update(overrides)
    return argparse.Namespace(**base)


def test_prune_backups_keeps_newest(tmp_path: Path) -> None:
    for name in (
        "full_20240101T000000Z.dump",
        "full_20240102T000000Z.dump",
        "full_20240103T000000Z.dump",
        "storage_20240101T000000Z.tar.gz",
    ):
        (tmp_path / name).write_bytes(b"x")
    pruned = db_cli.prune_backups(tmp_path, "full_", 2)
    assert [p.name for p in pruned] == ["full_20240101T000000Z.dump"]
    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert remaining == [
        "full_20240102T000000Z.dump",
        "full_20240103T000000Z.dump",
        "storage_20240101T000000Z.tar.gz",
    ]


def test_prune_backups_floors_keep_and_protects_fresh_files(tmp_path: Path) -> None:
    oldest = tmp_path / "full_20240101T000000Z.dump"
    oldest.write_bytes(b"x")
    (tmp_path / "full_20240102T000000Z.dump").write_bytes(b"x")
    (tmp_path / "full_20240103T000000Z.dump").write_bytes(b"x")
    # keep=0 floors to 1; the protected oldest file survives pruning.
    pruned = db_cli.prune_backups(tmp_path, "full_", 0, protect={oldest})
    assert [p.name for p in pruned] == ["full_20240102T000000Z.dump"]
    assert oldest.exists()


def test_dump_database_missing_binary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    error = db_cli.dump_database("postgresql://x", tmp_path / "full.dump")
    assert error is not None and "pg_dump not found" in error
    assert not (tmp_path / "full.dump").exists()


def test_dump_database_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/pg_dump")
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, b"", b"boom"),
    )
    error = db_cli.dump_database("postgresql://x", tmp_path / "full.dump")
    assert error is not None and "boom" in error


def test_dump_database_timeout(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/pg_dump")

    def _hang(*a, **k):
        raise subprocess.TimeoutExpired(cmd=a[0], timeout=3600)

    monkeypatch.setattr("subprocess.run", _hang)
    error = db_cli.dump_database("postgresql://x", tmp_path / "full.dump")
    assert error is not None and "timed out" in error


def test_snapshot_storage_skips_backups_dir(tmp_path: Path) -> None:
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "a.bin").write_bytes(b"data")
    (tmp_path / "backups").mkdir()
    (tmp_path / "backups" / "old.dump").write_bytes(b"old")
    target = tmp_path / "out" / "storage.tar.gz"
    target.parent.mkdir()
    db_cli.snapshot_storage(tmp_path, target, tmp_path / "out")
    names = tarfile.open(target).getnames()
    assert "documents" in names
    assert not any(n.startswith("backups") for n in names)


def test_snapshot_storage_skips_out_dir_inside_root(tmp_path: Path) -> None:
    (tmp_path / "documents").mkdir()
    out_dir = tmp_path / "nightly"
    out_dir.mkdir()
    (out_dir / "full_x.dump").write_bytes(b"x")
    target = out_dir / "storage.tar.gz"
    db_cli.snapshot_storage(tmp_path, target, out_dir)
    names = tarfile.open(target).getnames()
    assert "documents" in names
    assert "nightly" not in names


def test_cmd_backup_missing_pg_dump(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    code = db_cli._cmd_backup(_args(out_dir=str(tmp_path)))
    assert code == 3
    assert "pg_dump not found" in capsys.readouterr().out


def test_cmd_backup_success(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/pg_dump")

    def _ok(*a, **k):
        k["stdout"].write(b"DUMP")
        return subprocess.CompletedProcess(a[0], 0, b"", b"")

    monkeypatch.setattr("subprocess.run", _ok)
    storage = tmp_path / "storage"
    (storage / "documents").mkdir(parents=True)
    (storage / "documents" / "a.bin").write_bytes(b"data")
    (storage / "backups").mkdir()
    monkeypatch.setattr("app.cli.db.settings", _Settings(storage, tmp_path / "backups"))
    code = db_cli._cmd_backup(_args())
    assert code == 0
    dest = storage / "backups"
    dumps = sorted(dest.glob("full_*.dump"))
    tars = sorted(dest.glob("storage_*.tar.gz"))
    assert len(dumps) == 1 and dumps[0].read_bytes() == b"DUMP"
    assert len(tars) == 1


class _Settings:
    def __init__(self, storage: Path, _out: Path):
        self.STORAGE_LOCAL_PATH = str(storage)
        self.DATABASE_URL = "postgresql://x"


def test_backup_parser_wires_command() -> None:
    from app.cli.__main__ import build_parser

    args = build_parser().parse_args(["db", "backup", "--keep", "3", "--skip-storage"])
    assert args.db_command == "backup"
    assert args.keep == 3
    assert args.skip_storage is True
    assert callable(args.func)
