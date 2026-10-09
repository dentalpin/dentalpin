"""Every declared scheduled job actually runs (#629).

``test_scheduler_jobs.py`` asserts the job *ids* each module declares,
which catches a missing registration. It never calls them. That is how
``auto_close_expired_plans`` shipped querying a ``clinics.deleted_at``
column that does not exist (#628): the job raised ``UndefinedColumnError``
on its first statement every night at 03:00, APScheduler logged it, and
nothing else noticed — no test, no alert, no failing build.

So: resolve every declared job and call it. An empty database means most
jobs return after their first query, which makes this a schema-and-import
smoke test rather than behaviour coverage — deliberately, because that is
what stays cheap enough to run on every PR, and it is exactly the shape
of failure that went unseen. Behaviour belongs to the owning module's
own tests.

Two things worth knowing about the scope, raised on #629 and still open:

- Jobs that would reach a network with real data (``process_pec``,
  ``process_nav_submissions``, ``process_verifactu_submissions``,
  ``process_sistema_ts``) return early here because the DB is empty.
  That is luck, not a contract. If one of them ever grows a call before
  its first query, this test will start making outbound requests — so
  the empty DB is load-bearing and must stay that way.
- A job that catches its own exceptions broadly would pass this while
  doing nothing. This test cannot see that; it only proves the job does
  not raise.
"""

from __future__ import annotations

import pytest

from app.core.plugins.loader import register_discovered
from app.core.plugins.registry import module_registry


def _declared_jobs() -> list[tuple[str, object]]:
    """``[(label, job)]`` for every job every discovered module declares."""
    register_discovered()
    jobs: list[tuple[str, object]] = []
    for name, module in sorted(module_registry._modules.items()):
        for job in module.get_scheduled_jobs() or []:
            jobs.append((f"{name}:{job.id}", job))
    return jobs


_JOBS = _declared_jobs()


def test_there_are_jobs_to_exercise() -> None:
    """A collection bug would otherwise make this file pass vacuously."""
    assert len(_JOBS) >= 15, f"expected the scheduler's job set, got {len(_JOBS)}"


@pytest.mark.asyncio
@pytest.mark.parametrize("label,job", _JOBS, ids=[label for label, _ in _JOBS])
async def test_scheduled_job_runs_against_the_real_schema(db_session, label, job) -> None:
    """The regression shape from #628: the job died on its first
    statement, before touching a single row. No fixtures on purpose —
    that is how cheap catching it would have been."""
    await job.func()


def test_every_job_is_a_coroutine_function() -> None:
    """The scheduler awaits these. A sync function would be registered
    happily and then never actually do anything."""
    import inspect

    offenders = [label for label, job in _JOBS if not inspect.iscoroutinefunction(job.func)]
    assert not offenders, f"not async: {offenders}"
