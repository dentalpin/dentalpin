"""Agent tools for the supplier_ratings module. Thin wrappers over the service."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .service import SupplierRatingsService


class ListSupplierRatingsArgs(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class GetSupplierRatingArgs(BaseModel):
    supplier_id: str = Field(description="UUID of the supplier contact")


class CreateSupplierReviewArgs(BaseModel):
    supplier_id: str = Field(description="UUID of the supplier contact")
    score: int = Field(ge=1, le=5, description="1-5 communication rating")
    comment: str | None = Field(default=None, description="Optional note")


def _rating_summary(item: dict) -> dict:
    """Return native values — jsonify at the registry coerces UUID/Decimal."""
    metrics = item["metrics"]
    review = item["review"]
    return {
        "supplier_id": item["supplier_id"],
        "supplier_name": item["supplier_name"],
        "metrics": {
            "po_count": metrics.po_count,
            "received_count": metrics.received_count,
            "received_with_due_date": metrics.received_with_due_date,
            "on_time_deliveries": metrics.on_time_deliveries,
            "on_time_rate": metrics.on_time_rate,
            "received_quantity": metrics.received_quantity,
            "rejected_quantity": metrics.rejected_quantity,
            "reject_rate": metrics.reject_rate,
        },
        "review": (
            {
                "id": review.id,
                "supplier_id": review.supplier_id,
                "score": review.score,
                "comment": review.comment,
                "created_at": review.created_at,
                "updated_at": review.updated_at,
            }
            if review
            else None
        ),
    }


async def _list_supplier_ratings(ctx: AgentContext, params: ListSupplierRatingsArgs) -> dict:
    items, total = await SupplierRatingsService.list_ratings(
        ctx.db, ctx.clinic_id, params.page, params.page_size
    )
    return {
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "items": [_rating_summary(i) for i in items],
    }


async def _get_supplier_rating(ctx: AgentContext, params: GetSupplierRatingArgs) -> dict:
    item, _ = await SupplierRatingsService.get_ratings(
        ctx.db, ctx.clinic_id, UUID(params.supplier_id)
    )
    return _rating_summary(item)


async def _create_supplier_review(ctx: AgentContext, params: CreateSupplierReviewArgs) -> dict:
    from .schemas import SupplierReviewCreate

    # AgentContext carries no acting user (agent_id/session_id only).
    review = await SupplierRatingsService.create_review(
        ctx.db,
        ctx.clinic_id,
        SupplierReviewCreate(
            supplier_id=UUID(params.supplier_id), score=params.score, comment=params.comment
        ),
        created_by=None,
    )
    return {
        "id": review.id,
        "supplier_id": review.supplier_id,
        "score": review.score,
        "comment": review.comment,
    }


def get_all_tools() -> list[Tool]:
    return [
        Tool(
            name="list_supplier_ratings",
            description="List suppliers with delivery/quality metrics computed from purchase "
            "order history and their manual 1-5 communication rating",
            category=ToolCategory.READ,
            permissions=["supplier_ratings.read"],
            handler=_list_supplier_ratings,
            parameters=ListSupplierRatingsArgs,
            exposes_free_text=True,
        ),
        Tool(
            name="get_supplier_rating",
            description="Get the delivery/quality metrics and current manual rating for one supplier",
            category=ToolCategory.READ,
            permissions=["supplier_ratings.read"],
            handler=_get_supplier_rating,
            parameters=GetSupplierRatingArgs,
            exposes_free_text=True,
        ),
        Tool(
            name="create_supplier_review",
            description="Set the manual 1-5 communication rating for a supplier (one per supplier)",
            category=ToolCategory.WRITE,
            permissions=["supplier_ratings.write"],
            handler=_create_supplier_review,
            parameters=CreateSupplierReviewArgs,
            exposes_free_text=True,
        ),
    ]
