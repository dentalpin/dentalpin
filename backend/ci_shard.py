"""Deterministically distribute pytest items across independent CI jobs."""

import hashlib

import pytest


def pytest_addoption(parser):
    group = parser.getgroup("CI sharding")
    group.addoption("--ci-shard-count", type=int, default=1)
    group.addoption("--ci-shard-index", type=int, default=0)


def pytest_configure(config):
    count = config.getoption("--ci-shard-count")
    index = config.getoption("--ci-shard-index")
    if count < 1 or not 0 <= index < count:
        raise pytest.UsageError("CI shard count must be positive and index must be in range")


def shard_for(nodeid: str, count: int) -> int:
    """Use stable node IDs, independent of Python's randomized hash seed."""
    return int.from_bytes(hashlib.sha256(nodeid.encode("utf-8")).digest()[:8], "big") % count


def pytest_collection_modifyitems(config, items):
    count = config.getoption("--ci-shard-count")
    if count == 1:
        return
    index = config.getoption("--ci-shard-index")
    selected, deselected = [], []
    for item in items:
        (selected if shard_for(item.nodeid, count) == index else deselected).append(item)
    config.hook.pytest_deselected(items=deselected)
    items[:] = selected
