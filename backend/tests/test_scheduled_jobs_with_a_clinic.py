"""Every scheduled job's per-clinic body runs clean (#680).

``test_scheduled_jobs_run.py`` calls every job against an empty
database, so ``_list_clinics()`` returns nothing and the per-clinic body
never executes. And that body is wrapped in ``except Exception`` that
only logs, so a job broken for *every* clinic still returns normally —
APScheduler records a success. #628 (``clinics.deleted_at``) and #287
(``budgets.deleted_at``) were both that shape: a predicate on a column
that does not exist, which raises on execution whether or not any row
would match.

So one clinic is enough to make each body run its statements, and the
signal is the log, not an exception: a job here must not log anything
at WARNING or above.

Outbound connections are refused for the whole run, so a job that grows a
network call before its first query fails here instead of reaching the
internet (the concern the empty-DB test documents for its own scope).
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import pytest

from app.config import settings
from app.core.auth.models import Clinic
from tests.test_scheduled_jobs_run import _JOBS


@pytest.fixture
def no_outbound_network(monkeypatch):
    """Allow loopback, Unix sockets and the test database's host, nothing else.

    In docker-compose the database is ``db`` (a bridge address, not loopback).
    """
    db_host = urlparse(settings.DATABASE_URL).hostname or "localhost"
    db_addresses = {info[4][0] for info in socket.getaddrinfo(db_host, None)}
    real_connect = socket.socket.connect

    def guarded(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            host = address[0]
            try:
                loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                loopback = host == "localhost"
            if not loopback and host not in db_addresses:
                raise AssertionError(f"scheduled job tried to connect to {address!r}")
        return real_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)


@pytest.mark.asyncio
@pytest.mark.parametrize("label,job", _JOBS, ids=[label for label, _ in _JOBS])
async def test_scheduled_job_body_runs_clean_for_a_clinic(
    test_clinic: Clinic, caplog, no_outbound_network, label, job
) -> None:
    with caplog.at_level(logging.WARNING):
        await job.func()

    problems = [
        f"{r.levelname} {r.name}: {r.getMessage()}"
        for r in caplog.records
        if r.levelno >= logging.WARNING
    ]
    assert not problems, f"{label} logged instead of raising:\n" + "\n".join(problems)


def test_the_network_guard_refuses_a_public_address(no_outbound_network) -> None:
    """Without this the guard could stop applying and every job above
    would still pass. 192.0.2.1 is TEST-NET-1: refused before any packet."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(AssertionError, match="tried to connect"):
            sock.connect(("192.0.2.1", 443))
