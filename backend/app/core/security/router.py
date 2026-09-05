"""CSP violation report sink — ``POST /api/v1/security/csp-report``.

Browsers POST ``application/csp-report`` (legacy ``report-uri``) or
``application/reports+json`` here when the frontend's policy (Nitro
middleware, ``NUXT_CSP_MODE``) is violated. Reports are logged as
structured warnings — no table: the rollout step (#355) is "run
Report-Only in prod, read the logs, tighten, enforce", and a log line
per violation is what an operator greps. Public, no auth (the browser
sends nothing), rate-limited so a hostile page can't flood the log.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.core.auth.router import limiter

logger = logging.getLogger("dentalpin.csp")
router = APIRouter(prefix="/security", tags=["security"])

_MAX_BODY = 16 * 1024
_KEEP = (
    "document-uri",
    "violated-directive",
    "effective-directive",
    "blocked-uri",
    "source-file",
    "line-number",
    "disposition",
)


def _normalize(payload: Any) -> list[dict[str, Any]]:
    """Both wire formats → a flat list of the fields worth logging."""
    if isinstance(payload, dict) and "csp-report" in payload:
        payload = [payload["csp-report"]]
    elif isinstance(payload, list):  # Reporting API batches
        payload = [r.get("body", r) if isinstance(r, dict) else {} for r in payload]
    elif isinstance(payload, dict):
        payload = [payload]
    else:
        return []
    out = []
    for report in payload:
        if not isinstance(report, dict):
            continue
        # Reporting-API bodies use camelCase; legacy uses kebab-case.
        flat = {k.replace("_", "-"): v for k, v in report.items()}
        flat.update({_camel_to_kebab(k): v for k, v in report.items()})
        out.append({k: str(flat[k])[:300] for k in _KEEP if k in flat})
    return out


def _camel_to_kebab(name: str) -> str:
    return "".join(f"-{c.lower()}" if c.isupper() else c for c in name)


@router.post("/csp-report", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def csp_report(request: Request) -> Response:
    raw = await request.body()
    if len(raw) > _MAX_BODY:
        return Response(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return Response(status_code=status.HTTP_204_NO_CONTENT)  # accept-and-ignore
    for report in _normalize(payload):
        logger.warning("csp violation %s", json.dumps(report, sort_keys=True))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
