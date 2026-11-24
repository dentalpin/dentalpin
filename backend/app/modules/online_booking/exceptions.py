"""Booking domain errors and their HTTP transport mapping."""

from fastapi import HTTPException, Request
from fastapi.routing import APIRoute


class BookingError(Exception):
    """Base class for a rejected booking operation."""

    status_code = 400


class BookingNotFoundError(BookingError):
    """The clinic booking, request or patient is unavailable."""

    status_code = 404


class BookingConflictError(BookingError):
    """The operation conflicts with the current state or the agenda."""

    status_code = 409


class BookingGoneError(BookingError):
    """The confirmation link expired, was used, or never existed."""

    status_code = 410


class BookingValidationError(BookingError):
    """The supplied data is invalid for this clinic."""

    status_code = 422


class BookingForbiddenError(BookingError):
    """The caller lacks a permission this operation additionally needs."""

    status_code = 403


class BookingRateLimitedError(BookingError):
    """The contact exceeded its hourly request quota."""

    status_code = 429


class BookingUnavailableError(BookingError):
    """The confirmation email cannot be queued, so nothing was reserved."""

    status_code = 503


class CaptchaInvalidError(BookingError):
    """The ALTCHA proof is malformed, expired or not bound to this clinic."""

    status_code = 400


class CaptchaReusedError(BookingConflictError):
    """The ALTCHA proof was already consumed by an earlier request."""


class BookingRoute(APIRoute):
    """Map domain errors to HTTP so route functions only parse and delegate."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                return await handler(request)
            except BookingError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        return handle
