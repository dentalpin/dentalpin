"""integrations HTTP surface — mounted at ``/api/v1/integrations/``.

Admin CRUD for webhook subscriptions and API tokens, staff-
authenticated (``integrations.subscriptions.*``, ``integrations.
tokens.*``). Tokens are issued/revoked here but have no consumer
endpoint yet — the public data-read API (issue #65 §2, §11) that
would authenticate with them is follow-up scope — see
notes/dentalpin/65-integrations-api.md "Scope reality check".
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .schemas import (
    ApiTokenCreate,
    ApiTokenCreated,
    ApiTokenResponse,
    WebhookSubscriptionCreate,
    WebhookSubscriptionCreated,
    WebhookSubscriptionResponse,
    WebhookSubscriptionUpdate,
)
from .service import IntegrationsService

router = APIRouter()


async def _get_owned_subscription(db: AsyncSession, clinic_id: UUID, subscription_id: UUID):
    subscription = await IntegrationsService.get_subscription(db, clinic_id, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return subscription


async def _get_owned_token(db: AsyncSession, clinic_id: UUID, token_id: UUID):
    token = await IntegrationsService.get_token(db, clinic_id, token_id)
    if token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    return token


@router.get(
    "/webhooks/subscriptions", response_model=ApiResponse[list[WebhookSubscriptionResponse]]
)
async def list_subscriptions(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("integrations.subscriptions.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[WebhookSubscriptionResponse]]:
    subscriptions = await IntegrationsService.list_subscriptions(db, ctx.clinic_id)
    return ApiResponse(data=[WebhookSubscriptionResponse.model_validate(s) for s in subscriptions])


@router.post(
    "/webhooks/subscriptions",
    response_model=ApiResponse[WebhookSubscriptionCreated],
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    data: WebhookSubscriptionCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("integrations.subscriptions.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[WebhookSubscriptionCreated]:
    subscription, secret = await IntegrationsService.create_subscription(
        db, ctx.clinic_id, data.model_dump()
    )
    response = WebhookSubscriptionCreated(
        **WebhookSubscriptionResponse.model_validate(subscription).model_dump(),
        secret=secret,
    )
    return ApiResponse(
        data=response,
        message="Store the secret now — it will not be shown again.",
    )


@router.patch(
    "/webhooks/subscriptions/{subscription_id}",
    response_model=ApiResponse[WebhookSubscriptionResponse],
)
async def update_subscription(
    subscription_id: UUID,
    data: WebhookSubscriptionUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("integrations.subscriptions.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[WebhookSubscriptionResponse]:
    subscription = await _get_owned_subscription(db, ctx.clinic_id, subscription_id)
    subscription = await IntegrationsService.update_subscription(
        db, subscription, data.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=WebhookSubscriptionResponse.model_validate(subscription))


@router.delete("/webhooks/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("integrations.subscriptions.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    subscription = await _get_owned_subscription(db, ctx.clinic_id, subscription_id)
    await IntegrationsService.delete_subscription(db, subscription)


@router.get("/tokens", response_model=ApiResponse[list[ApiTokenResponse]])
async def list_tokens(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("integrations.tokens.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[ApiTokenResponse]]:
    tokens = await IntegrationsService.list_tokens(db, ctx.clinic_id)
    return ApiResponse(data=[ApiTokenResponse.model_validate(t) for t in tokens])


@router.post(
    "/tokens",
    response_model=ApiResponse[ApiTokenCreated],
    status_code=status.HTTP_201_CREATED,
)
async def create_token(
    data: ApiTokenCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("integrations.tokens.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ApiTokenCreated]:
    token, plaintext = await IntegrationsService.create_token(db, ctx.clinic_id, data.model_dump())
    response = ApiTokenCreated(
        **ApiTokenResponse.model_validate(token).model_dump(),
        token=plaintext,
    )
    return ApiResponse(
        data=response,
        message="Store the token now — it will not be shown again.",
    )


@router.post("/tokens/{token_id}/revoke", response_model=ApiResponse[ApiTokenResponse])
async def revoke_token(
    token_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("integrations.tokens.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ApiTokenResponse]:
    token = await _get_owned_token(db, ctx.clinic_id, token_id)
    if token.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Token already revoked")
    token = await IntegrationsService.revoke_token(db, token)
    return ApiResponse(data=ApiTokenResponse.model_validate(token))
