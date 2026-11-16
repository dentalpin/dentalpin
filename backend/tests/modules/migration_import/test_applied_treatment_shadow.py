"""Shadow-dedup pre-pass for the applied_treatment mapper.

We don't spin up the full mapper pipeline here — just feed
``_ensure_shadow_index`` a fake ``ctx.handle`` whose ``entity_iter``
yields the (canonical_uuid, src_id, src_sys, payload_json, raw_json,
ts) tuples the real DPMF reader emits, and assert the planned twin is
correctly identified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.modules.migration_import.mappers.applied_treatment import AppliedTreatmentMapper


@dataclass
class _StubHandle:
    rows: list[tuple[str, str, str, str, str, str | None]]

    def entity_iter(self, entity_type: str):
        assert entity_type == "applied_treatment"
        yield from self.rows


@dataclass
class _StubCtx:
    handle: _StubHandle | None


def _row(
    canonical_uuid: str,
    *,
    patient_uuid: str,
    status_code: int,
    start_date: str,
    end_date: str | None = None,
    budget_line_uuid: str | None = None,
    id_tto: int | None = None,
    id_tipo_odg: int | None = None,
    teeth: list[int] | None = None,
) -> tuple[str, str, str, str, str, None]:
    payload: dict[str, Any] = {
        "patient_uuid": patient_uuid,
        "status_code": status_code,
        "start_date": start_date,
        "end_date": end_date,
        "teeth": teeth or [],
    }
    if budget_line_uuid is not None:
        payload["budget_line_uuid"] = budget_line_uuid
    raw: dict[str, Any] = {}
    if id_tto is not None:
        raw["IdTto"] = id_tto
        # Real DPMF: a Gesdén IdTto always ships as a catalog variant.
        payload["treatment_variant_uuid"] = f"variant-{id_tto}"
    if id_tipo_odg is not None:
        raw["IdTipoOdg"] = id_tipo_odg
    return (canonical_uuid, "src", "gesden", json.dumps(payload), json.dumps(raw), None)


def test_shadow_pairs_by_budget_line_uuid_even_when_id_tto_differs() -> None:
    """The new primary key. Two TtosMed rows that share IdPresuTto but
    differ on IdTto (tariff edited between plan-creation and execution)
    must pair as planned→performed. The legacy key would have missed
    this pair entirely."""
    patient = str(uuid4())
    budget_line = str(uuid4())
    planned_uuid = str(uuid4())
    performed_uuid = str(uuid4())

    handle = _StubHandle(
        rows=[
            _row(
                planned_uuid,
                patient_uuid=patient,
                status_code=3,
                start_date="2024-01-15",
                budget_line_uuid=budget_line,
                id_tto=101,  # original tariff
                id_tipo_odg=22,
                teeth=[16],
            ),
            _row(
                performed_uuid,
                patient_uuid=patient,
                status_code=5,
                start_date="2024-03-02",
                end_date="2024-03-02",
                budget_line_uuid=budget_line,
                id_tto=102,  # tariff edited; legacy key would NOT match
                id_tipo_odg=22,
                teeth=[16],
            ),
        ]
    )

    mapper = AppliedTreatmentMapper()
    shadow = mapper._ensure_shadow_index(_StubCtx(handle=handle))  # type: ignore[arg-type]

    assert shadow == {planned_uuid: performed_uuid}


def test_shadow_falls_back_to_legacy_key_without_budget_line() -> None:
    """Rows with no budget_line_uuid still pair on (patient, IdTto,
    IdTipoOdg, teeth) within the 24-month window."""
    patient = str(uuid4())
    planned_uuid = str(uuid4())
    performed_uuid = str(uuid4())

    handle = _StubHandle(
        rows=[
            _row(
                planned_uuid,
                patient_uuid=patient,
                status_code=3,
                start_date="2024-01-15",
                id_tto=101,
                id_tipo_odg=22,
                teeth=[16],
            ),
            _row(
                performed_uuid,
                patient_uuid=patient,
                status_code=5,
                start_date="2024-03-02",
                end_date="2024-03-02",
                id_tto=101,
                id_tipo_odg=22,
                teeth=[16],
            ),
        ]
    )

    mapper = AppliedTreatmentMapper()
    shadow = mapper._ensure_shadow_index(_StubCtx(handle=handle))  # type: ignore[arg-type]

    assert shadow == {planned_uuid: performed_uuid}


def test_shadow_does_not_pair_unrelated_rows() -> None:
    """Rows that share neither IdPresuTto nor the legacy tuple must
    stay unpaired."""
    patient = str(uuid4())
    a = str(uuid4())
    b = str(uuid4())

    handle = _StubHandle(
        rows=[
            _row(
                a,
                patient_uuid=patient,
                status_code=3,
                start_date="2024-01-15",
                id_tto=101,
                id_tipo_odg=22,
                teeth=[16],
            ),
            _row(
                b,
                patient_uuid=patient,
                status_code=5,
                start_date="2024-03-02",
                end_date="2024-03-02",
                id_tto=999,  # different IdTto
                id_tipo_odg=26,  # different IdTipoOdg
                teeth=[17],  # different tooth
            ),
        ]
    )

    mapper = AppliedTreatmentMapper()
    shadow = mapper._ensure_shadow_index(_StubCtx(handle=handle))  # type: ignore[arg-type]

    assert shadow == {}


def test_shadow_handles_null_tipo_odg_in_legacy_key() -> None:
    """Removing the early ``continue`` on null IdTipoOdg means legacy
    rows with no IdTipoOdg can still match siblings that also have no
    IdTipoOdg. The dict key tolerates None on either side."""
    patient = str(uuid4())
    planned_uuid = str(uuid4())
    performed_uuid = str(uuid4())

    handle = _StubHandle(
        rows=[
            _row(
                planned_uuid,
                patient_uuid=patient,
                status_code=3,
                start_date="2024-01-15",
                id_tto=101,
                id_tipo_odg=None,
                teeth=[],
            ),
            _row(
                performed_uuid,
                patient_uuid=patient,
                status_code=5,
                start_date="2024-03-02",
                end_date="2024-03-02",
                id_tto=101,
                id_tipo_odg=None,
                teeth=[],
            ),
        ]
    )

    mapper = AppliedTreatmentMapper()
    shadow = mapper._ensure_shadow_index(_StubCtx(handle=handle))  # type: ignore[arg-type]

    assert shadow == {planned_uuid: performed_uuid}


def test_shadow_never_pairs_rows_routed_to_notes() -> None:
    """Free-text notes (no IdTto, no clinical IdTipoOdg) all share the
    legacy key (patient, None, None, ()). An unfinished note must not be
    swallowed as the "planned twin" of a later one, nor of a non-clinical
    entry such as IdTipoOdg=11 (Anotación)."""
    patient = str(uuid4())
    note_a, note_b, anot_a, anot_b = (str(uuid4()) for _ in range(4))

    handle = _StubHandle(
        rows=[
            _row(note_a, patient_uuid=patient, status_code=0, start_date="2024-01-15"),
            _row(
                note_b,
                patient_uuid=patient,
                status_code=5,
                start_date="2024-03-02",
                end_date="2024-03-02",
            ),
            _row(
                anot_a, patient_uuid=patient, status_code=0, start_date="2024-01-15", id_tipo_odg=11
            ),
            _row(
                anot_b,
                patient_uuid=patient,
                status_code=5,
                start_date="2024-03-02",
                end_date="2024-03-02",
                id_tipo_odg=11,
            ),
        ]
    )

    mapper = AppliedTreatmentMapper()
    shadow = mapper._ensure_shadow_index(_StubCtx(handle=handle))  # type: ignore[arg-type]

    assert shadow == {}
