"""Module entry point for ``python -m app.cli``."""

from __future__ import annotations

import argparse
import asyncio
import sys

from . import db as db_cli
from . import mfa as mfa_cli
from . import modules as modules_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dentalpin",
        description="DentalPin admin CLI. Run inside the backend container.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    modules_cli.register(sub)
    db_cli.register(sub)
    mfa_cli.register(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 1

    result = handler(args)
    if asyncio.iscoroutine(result):
        return asyncio.run(result) or 0
    return int(result or 0)


if __name__ == "__main__":
    sys.exit(main())
