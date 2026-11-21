"""Document domain errors and their HTTP transport mapping."""

from fastapi import HTTPException, Request
from fastapi.routing import APIRoute


class ConsentError(Exception):
    """Base class for a rejected consent operation."""


class ConsentNotFoundError(ConsentError):
    """A consent, link, patient, template or evidence is unavailable."""


class ConsentConflictError(ConsentError):
    """A consent operation conflicts with its current state or evidence."""


class ConsentValidationError(ConsentError):
    """The supplied consent data is invalid."""


class ConsentStorageError(ConsentError):
    """The signed PDF could not be safely rendered or stored."""


class ConsentRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                return await handler(request)
            except ConsentError as exc:
                codes = {
                    ConsentNotFoundError: 404,
                    ConsentConflictError: 409,
                    ConsentValidationError: 422,
                    ConsentStorageError: 500,
                }
                raise HTTPException(status_code=codes.get(type(exc), 500), detail=str(exc)) from exc

        return handle
