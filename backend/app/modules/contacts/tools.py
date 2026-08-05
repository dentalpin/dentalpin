"""Agent tools for the contacts module. Thin wrappers over ContactService."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import ContactCreate, ContactType
from .service import ContactService


class ListContactsArgs(BaseModel):
    contact_type: ContactType | None = None
    search: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class CreateContactArgs(BaseModel):
    name: str
    contact_type: ContactType
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None


def _contact_summary(contact) -> dict:
    return {
        "id": str(contact.id),
        "name": contact.name,
        "contact_type": contact.contact_type,
        "phone": contact.phone,
        "email": contact.email,
    }


async def _list_contacts(ctx: AgentContext, params: ListContactsArgs) -> dict:
    items, total = await ContactService.list_contacts(
        ctx.db,
        ctx.clinic_id,
        contact_type=params.contact_type,
        search=params.search,
        page=1,
        page_size=params.limit,
    )
    return {"total": total, "contacts": [_contact_summary(c) for c in items]}


async def _create_contact(ctx: AgentContext, params: CreateContactArgs) -> dict:
    payload = ContactCreate(
        name=params.name,
        contact_type=params.contact_type,
        phone=params.phone,
        email=params.email,
        address=params.address,
        notes=params.notes,
    )
    contact = await ContactService.create_contact(ctx.db, ctx.clinic_id, payload)
    return _contact_summary(contact)


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_contacts",
            description="List external lab/supplier/provider contacts, optionally filtered by type or name search.",
            parameters=ListContactsArgs,
            handler=_list_contacts,
            permissions=["contacts.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="create_contact",
            description="Add a new external lab, supplier, or other provider contact.",
            parameters=CreateContactArgs,
            handler=_create_contact,
            permissions=["contacts.write"],
            category=ToolCategory.WRITE,
        ),
    ]
