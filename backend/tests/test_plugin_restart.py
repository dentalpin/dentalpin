"""Module-restart shutdown behavior (#526).

An unsupervised backend (PermissionError signalling PID 1) must stay
up: pending module operations are durable and apply on the next boot,
so self-killing buys nothing and takes the API down.
"""

import logging
import os
import signal

import pytest

from app.core.plugins.router import _graceful_exit


@pytest.mark.asyncio
async def test_graceful_exit_signals_pid1(monkeypatch) -> None:
    """Supervised path: exactly one kill, aimed at PID 1."""
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: calls.append((pid, sig)))
    await _graceful_exit()
    assert calls == [(1, signal.SIGTERM)]


@pytest.mark.asyncio
async def test_graceful_exit_never_kills_self_on_permission_error(monkeypatch, caplog) -> None:
    """Unsupervised path: no self-kill, an actionable error instead."""
    calls: list[tuple[int, int]] = []

    def _kill(pid: int, sig: int) -> None:
        calls.append((pid, sig))
        if pid == 1:
            raise PermissionError

    monkeypatch.setattr(os, "kill", _kill)
    with caplog.at_level(logging.ERROR):
        await _graceful_exit()
    assert calls == [(1, signal.SIGTERM)]
    assert "Restart the backend yourself" in caplog.text
