"""Uninstall round-trip test for the documents module.

Covers the ``removable=True`` contract: downgrade the ``documents``
branch to base, verify tables are gone, re-upgrade, verify tables
return, and confirm no other module's tables were affected.
"""

import pytest

pytestmark = pytest.mark.alembic_roundtrip


@pytest.mark.asyncio
async def test_uninstall_roundtrip(alembic_roundtrip):
    """Downgrade → upgrade on the ``documents`` branch.

    The ``alembic_roundtrip`` fixture handles:
    - snapshotting ``information_schema.tables`` before
    - ``alembic downgrade documents@-1`` (remove module tables)
    - verifying ``generated_documents`` is gone
    - ``alembic upgrade documents@head`` (re-create)
    - verifying ``generated_documents`` is back
    - verifying no other module's table disappeared
    - checking the pg_dump backup file is non-empty
    """
    # The fixture drives the full round-trip; the test body is
    # intentionally minimal — any additional assertions about the
    # module's specific tables go here.
    pass
