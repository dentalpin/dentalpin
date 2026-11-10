"""A tool parameter over a closed vocabulary must advertise its values (#679).

A status or type filter typed as ``str`` fails in the one way a caller
cannot notice: ``tool_registry.call`` has nothing to reject, so an
unrecognized value reaches the query as ``WHERE status = 'whatever'`` and
comes back ``ok`` with an empty result. An agent reads that as "there are
none" and reports it as fact; an error would have made it try again. Typing
the parameter with the module's own ``Literal`` alias puts the vocabulary in
the schema the model is shown *and* turns a bad value into a validation
error naming the field.

Companion to ``test_tool_param_types.py``, which covers the same contract
for ``UUID`` and ``date``.
"""

from __future__ import annotations

from types import UnionType
from typing import Annotated, Union, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

from app.core.agents.tools import tool_registry
from app.core.plugins.loader import module_registry, register_discovered

# Parameters whose name reads like a closed vocabulary but which genuinely
# accept open text. Every entry is a claim that no enum exists to advertise —
# keep it annotated, and prefer typing the parameter over adding a line here.
OPEN_VOCABULARY_PARAMS: frozenset[str] = frozenset(
    {
        # Any module's event name reaches the journal, so the vocabulary is
        # the whole event catalog rather than this module's own.
        "activity_journal.search_activity.event_type",
        # Retention policies may be written for any category; only
        # email|phone|identity are erasable, and the service says so.
        "gdpr.create_retention_policy.data_category",
    }
)


def _registered_tools() -> list[tuple[str, type[BaseModel]]]:
    """Every discovered module's tools, namespaced, with their parameter model."""
    register_discovered()
    tool_registry.clear()
    for module in module_registry.list_discovered():
        tool_registry.register_from(module)
    return [(q, tool_registry.get(q).parameters) for q in tool_registry.list()]


def _looks_like_a_vocabulary(name: str) -> bool:
    return (
        name == "status"
        or name.endswith("_status")
        or name.endswith("_type")
        or name == "category"
        or name.endswith("_category")
    )


def _is_plain_str(annotation) -> bool:
    """True when the annotation admits any string, i.e. carries no enum."""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        return any(_is_plain_str(a) for a in get_args(annotation) if a is not type(None))
    return annotation is str


def test_vocabulary_parameters_are_literal_typed() -> None:
    offenders = []
    checked = 0
    for qualified, model in _registered_tools():
        for name, field in model.model_fields.items():
            if not _looks_like_a_vocabulary(name):
                continue
            if f"{qualified}.{name}" in OPEN_VOCABULARY_PARAMS:
                continue
            checked += 1
            if _is_plain_str(field.annotation):
                offenders.append(f"{qualified}.{name}: {field.annotation}")

    # Floor: if discovery or registration silently returns nothing, an empty
    # offender list would otherwise read as a pass.
    assert checked > 20, f"only {checked} vocabulary params inspected — registration broke"
    assert not offenders, (
        "status/type parameters typed as bare str — an unknown value filters "
        "the result to nothing instead of being rejected:\n" + "\n".join(sorted(offenders))
    )


def test_open_vocabulary_entries_are_still_open() -> None:
    """Every exemption names a real parameter that is still a bare str.

    An entry left behind after its parameter gained a Literal exempts the
    parameter from the check above, so a later revert to ``str`` would pass.
    """
    fields = {
        f"{qualified}.{name}": field.annotation
        for qualified, model in _registered_tools()
        for name, field in model.model_fields.items()
    }
    stale = sorted(
        entry
        for entry in OPEN_VOCABULARY_PARAMS
        if entry not in fields or not _is_plain_str(fields[entry])
    )
    assert not stale, "OPEN_VOCABULARY_PARAMS entries that are gone or now typed: " + ", ".join(
        stale
    )


@pytest.mark.parametrize(
    "qualified,field",
    [
        ("gdpr.list_gdpr_requests", "status"),
        ("gdpr.list_gdpr_requests", "request_type"),
        ("purchase_orders.list_purchase_orders", "order_status"),
        ("imaging_viewer.list_rvg_imports", "status"),
    ],
)
def test_unknown_filter_value_is_rejected_by_name(qualified: str, field: str) -> None:
    """The chokepoint must name the field rather than answer an empty list."""
    _registered_tools()
    model = tool_registry.get(qualified).parameters
    with pytest.raises(ValidationError) as exc:
        model(**{field: "pending_approval"})
    assert any(e["loc"] == (field,) for e in exc.value.errors()), exc.value.errors()


@pytest.mark.parametrize(
    "qualified,field",
    [
        ("gdpr.list_gdpr_requests", "status"),
        ("purchase_orders.list_purchase_orders", "order_status"),
        ("imaging_viewer.list_rvg_imports", "status"),
    ],
)
def test_filter_schema_lists_its_values(qualified: str, field: str) -> None:
    """The model has to see the vocabulary to pick a value from it."""
    _registered_tools()
    schema = tool_registry.get(qualified).parameters.model_json_schema()
    prop = schema["properties"][field]
    variants = [
        schema["$defs"][v["$ref"].split("/")[-1]] if "$ref" in v else v
        for v in prop.get("anyOf", [prop])
    ]
    assert any(v.get("enum") for v in variants), prop


def test_purchase_order_status_aliases_cannot_drift() -> None:
    """The Literal and the membership set are one vocabulary, not two.

    ``received`` is reachable only through a receive batch that fulfils every
    line, so it is never a transition target — the matrix in the service is
    the authority for that, and the alias the agent is typed with has to
    agree with it.
    """
    from app.modules.purchase_orders.models import (
        PO_STATUSES,
        PurchaseOrderStatus,
        PurchaseOrderTransitionTarget,
    )
    from app.modules.purchase_orders.service import ALLOWED_TRANSITIONS

    assert PO_STATUSES == frozenset(get_args(PurchaseOrderStatus))

    reachable = frozenset().union(*ALLOWED_TRANSITIONS.values())
    assert frozenset(get_args(PurchaseOrderTransitionTarget)) == reachable
    assert "received" not in get_args(PurchaseOrderTransitionTarget)
