"""A value wider than its column answers 422, not 500.

Request schemas don't all mirror their column widths (NUMERIC(10,2) prices,
VARCHAR(n) codes), so Postgres is the last check. Its data exceptions are the
client's to fix. The end-to-end case (a catalog price) lives in
``test_catalog.py`` next to its fixture.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import DBAPIError
from starlette.requests import Request

from app.main import db_data_exception_handler


def _db_error(sqlstate: str) -> DBAPIError:
    return DBAPIError("INSERT ...", {}, SimpleNamespace(sqlstate=sqlstate))


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


@pytest.mark.asyncio
async def test_text_past_the_column_answers_422():
    response = await db_data_exception_handler(_request(), _db_error("22001"))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_other_database_errors_stay_500():
    response = await db_data_exception_handler(_request(), _db_error("40P01"))
    assert response.status_code == 500
