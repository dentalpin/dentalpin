"""CSP report sink (#355): both wire formats land as structured log lines."""

import json
import logging

import pytest
from httpx import AsyncClient

URL = "/api/v1/security/csp-report"


@pytest.mark.asyncio
async def test_legacy_report_uri_format_is_logged(client: AsyncClient, caplog) -> None:
    body = {
        "csp-report": {
            "document-uri": "https://clinic.example/agenda",
            "violated-directive": "script-src",
            "blocked-uri": "https://evil.example/x.js",
            "line-number": 12,
        }
    }
    with caplog.at_level(logging.WARNING, logger="dentalpin.csp"):
        res = await client.post(
            URL, content=json.dumps(body), headers={"content-type": "application/csp-report"}
        )
    assert res.status_code == 204
    line = next(r for r in caplog.records if "csp violation" in r.getMessage())
    logged = json.loads(line.getMessage().split("csp violation ", 1)[1])
    assert logged["violated-directive"] == "script-src"
    assert logged["blocked-uri"] == "https://evil.example/x.js"


@pytest.mark.asyncio
async def test_reporting_api_batch_format_is_logged(client: AsyncClient, caplog) -> None:
    body = [
        {
            "type": "csp-violation",
            "body": {
                "documentURL": "https://clinic.example/",
                "effectiveDirective": "img-src",
                "blockedURL": "https://cdn.example/a.png",
                "disposition": "report",
            },
        }
    ]
    with caplog.at_level(logging.WARNING, logger="dentalpin.csp"):
        res = await client.post(
            URL, content=json.dumps(body), headers={"content-type": "application/reports+json"}
        )
    assert res.status_code == 204
    line = next(r for r in caplog.records if "csp violation" in r.getMessage())
    logged = json.loads(line.getMessage().split("csp violation ", 1)[1])
    assert logged["effective-directive"] == "img-src"
    assert logged["disposition"] == "report"


@pytest.mark.asyncio
async def test_garbage_is_accepted_and_ignored(client: AsyncClient) -> None:
    res = await client.post(URL, content=b"not json", headers={"content-type": "text/plain"})
    assert res.status_code == 204
    res = await client.post(URL, content=b"x" * (17 * 1024))
    assert res.status_code == 413
