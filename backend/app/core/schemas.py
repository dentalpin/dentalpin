"""Core schemas for standardized API responses."""

from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel

T = TypeVar("T")
V = TypeVar("V")


def _reject_null(value):
    if value is None:
        raise ValueError("cannot be null; omit the field to keep its current value")
    return value


# For PATCH schemas: ``field: NotNull[str] = None`` may be omitted (the
# default is never validated, so ``exclude_unset`` leaves the column
# alone) but an explicit ``null`` is a 422 naming the field, instead of
# reaching a NOT NULL column as a 500 (#976).
NotNull = Annotated[V | None, AfterValidator(_reject_null)]


class ApiResponse(BaseModel, Generic[T]):
    """Wrapper for individual item responses."""

    data: T
    message: str | None = None


class PaginatedApiResponse(BaseModel, Generic[T]):
    """Wrapper for paginated list responses."""

    data: list[T]
    total: int
    page: int
    page_size: int
    message: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    data: None = None
    message: str
    errors: list[str] = []
