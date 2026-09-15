"""Per-request logging context — contextvars + log filter.

A single ``request_id`` ties together every log line and every event
fired during one HTTP request, including background-task work
spawned inside the request handler (because ``contextvars`` propagate
across ``asyncio`` tasks by default). ``clinic_id`` and ``user_id``
join the record once auth resolves them.

The filter writes the values onto every ``LogRecord`` as plain
attributes — formatters refer to them via ``%(request_id)s`` etc.,
and JSON formatters pick them up automatically. Default values (``-``)
mean unbound, so format strings don't crash on logs emitted outside a
request (startup, cron, REPL).

Read-only callers can fetch the current value via ``get_request_id``.
Setters return a ``Token`` so the value can be restored on the way
out — the middleware uses this for cleanup; library code should
prefer ``bind`` as a context manager.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from contextvars import ContextVar, Token
from uuid import UUID, uuid4

_UNBOUND = "-"

REQUEST_ID: ContextVar[str] = ContextVar("request_id", default=_UNBOUND)
CLINIC_ID: ContextVar[str] = ContextVar("clinic_id", default=_UNBOUND)
USER_ID: ContextVar[str] = ContextVar("user_id", default=_UNBOUND)


def new_request_id() -> str:
    """Return a fresh short id suitable for ``X-Request-Id``."""
    return uuid4().hex[:16]


def get_request_id() -> str:
    return REQUEST_ID.get()


def set_request_context(
    *,
    request_id: str | None = None,
    clinic_id: str | UUID | None = None,
    user_id: str | UUID | None = None,
) -> list[Token]:
    """Bind any subset of the trio. Returns reset tokens (caller resets)."""
    tokens: list[Token] = []
    if request_id is not None:
        tokens.append(REQUEST_ID.set(request_id))
    if clinic_id is not None:
        tokens.append(CLINIC_ID.set(str(clinic_id)))
    if user_id is not None:
        tokens.append(USER_ID.set(str(user_id)))
    return tokens


def reset_request_context(tokens: list[Token]) -> None:
    """Reset every contextvar in the order opposite to ``set``."""
    for tok in reversed(tokens):
        # Token.var is the ContextVar that produced the token.
        tok.var.reset(tok)


@contextlib.contextmanager
def bind(
    *,
    request_id: str | None = None,
    clinic_id: str | UUID | None = None,
    user_id: str | UUID | None = None,
) -> Iterator[None]:
    """Context-manager flavour of ``set_request_context`` for library
    code that wants a local override (cron jobs, agent tools, etc.)."""
    tokens = set_request_context(request_id=request_id, clinic_id=clinic_id, user_id=user_id)
    try:
        yield
    finally:
        reset_request_context(tokens)


class LogContextFilter(logging.Filter):
    """Inject ``request_id`` / ``clinic_id`` / ``user_id`` onto every
    record so formatters can render them without each call-site having
    to pass ``extra={...}``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # ``setattr`` only when missing so explicit ``extra={"clinic_id": ...}``
        # passed by the caller still wins.
        if not hasattr(record, "request_id"):
            record.request_id = REQUEST_ID.get()
        if not hasattr(record, "clinic_id"):
            record.clinic_id = CLINIC_ID.get()
        if not hasattr(record, "user_id"):
            record.user_id = USER_ID.get()
        return True


_DEFAULT_FORMAT = (
    "%(asctime)s %(levelname)-7s [req=%(request_id)s clinic=%(clinic_id)s] %(name)s: %(message)s"
)


def setup_logging(level: int | str = logging.INFO) -> None:
    """Attach the context filter to the root logger and set a format
    string that surfaces the bound fields. Idempotent.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Replace formatter on every existing handler (uvicorn installs
    # its own at import time) and ensure the filter is attached so
    # extras land on every record reaching the handler.
    filt = LogContextFilter()
    formatter = logging.Formatter(_DEFAULT_FORMAT)
    for handler in root.handlers:
        handler.setFormatter(formatter)
        # Don't add the filter twice on reload.
        if not any(isinstance(f, LogContextFilter) for f in handler.filters):
            handler.addFilter(filt)

    # Also attach a stream handler if uvicorn somehow didn't (tests,
    # REPL). Avoid duplicate handlers.
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.addFilter(filt)
        root.addHandler(handler)


def setup_error_tracking(dsn: str = "", traces_sample_rate: float = 0.1) -> bool:
    """Attach Sentry (or any Sentry-protocol backend, e.g. self-hosted
    GlitchTip) when a DSN is configured. Returns True when attached.

    No-op (False) without a DSN or without ``sentry_sdk`` installed, and
    never raises — error reporting must not break boot. PII is never
    attached (``send_default_pii=False``): clinic data stays out of
    error payloads by construction.
    """
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logging.getLogger(__name__).warning(
            "SENTRY_DSN is set but sentry_sdk is not installed; error tracking off"
        )
        return False
    try:
        sentry_sdk.init(
            dsn=dsn,
            send_default_pii=False,
            traces_sample_rate=traces_sample_rate,
        )
    except Exception:
        logging.getLogger(__name__).exception("sentry_sdk.init failed; error tracking off")
        return False
    return True
