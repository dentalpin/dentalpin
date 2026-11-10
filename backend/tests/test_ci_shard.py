"""CI shard selection must be deterministic and preserve every test."""

from types import SimpleNamespace

import pytest

from ci_shard import pytest_collection_modifyitems, pytest_configure, shard_for


def test_shards_are_disjoint_and_complete():
    nodeids = [f"tests/test_sample.py::test_case[{i}]" for i in range(300)]
    for count in (1, 2, 4, 7):
        shards = [
            {nodeid for nodeid in nodeids if shard_for(nodeid, count) == i} for i in range(count)
        ]
        assert set.union(*shards) == set(nodeids)
        assert sum(map(len, shards)) == len(nodeids)
    assert shard_for("tests/test.py::test_1", 4) == 1


@pytest.mark.parametrize("count,index", [(0, 0), (-1, 0), (2, -1), (2, 2)])
def test_invalid_shards_fail_closed(count, index):
    values = {"--ci-shard-count": count, "--ci-shard-index": index}
    with pytest.raises(pytest.UsageError):
        pytest_configure(SimpleNamespace(getoption=values.__getitem__))


def test_selection_preserves_order_and_reports_deselection():
    items = [SimpleNamespace(nodeid=f"tests/test.py::test_{i}") for i in range(20)]
    original = list(items)
    seen = []
    values = {"--ci-shard-count": 2, "--ci-shard-index": 0}
    config = SimpleNamespace(
        getoption=values.__getitem__,
        hook=SimpleNamespace(pytest_deselected=lambda items: seen.extend(items)),
    )
    pytest_collection_modifyitems(config, items)
    assert items == [item for item in original if shard_for(item.nodeid, 2) == 0]
    assert seen == [item for item in original if shard_for(item.nodeid, 2) == 1]
