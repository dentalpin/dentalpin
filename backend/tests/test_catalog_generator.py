"""Guards for the events-catalog publisher scan (audit S4, #94).

The catalog generator used to only resolve `event_bus.publish(EventType.X)`
and string literals, so events published via a module-local enum
(`OdontogramEventType`) or a dispatch variable (agenda status map,
clinical_notes note-type map, notifications gateway) were reported as
having *no publisher* — inviting someone to delete a live event. These
tests lock in that each of those four mechanisms is now attributed.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import app

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_catalogs.py"


def _load_generator():
    # The generator derives its roots from the script location, which is
    # wrong when the backend is mounted at a non-repo path (e.g. /app in
    # the container). Pin the roots to the actual ``app`` package so the
    # source scan works regardless of layout.
    backend_root = Path(app.__file__).resolve().parents[1]
    prev_backend_root = os.environ.get("DENTALPIN_BACKEND_ROOT")
    prev_repo_root = os.environ.get("DENTALPIN_REPO_ROOT")
    os.environ["DENTALPIN_BACKEND_ROOT"] = str(backend_root)
    os.environ["DENTALPIN_REPO_ROOT"] = str(backend_root.parent)
    try:
        spec = importlib.util.spec_from_file_location("_gen_catalogs", _SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        # Restore rather than leak the override — other tests in the same
        # session (e.g. test_module_docs.py's docs_coverage fixture) read
        # this same env var and must not see it repointed at "/".
        if prev_backend_root is None:
            os.environ.pop("DENTALPIN_BACKEND_ROOT", None)
        else:
            os.environ["DENTALPIN_BACKEND_ROOT"] = prev_backend_root
        if prev_repo_root is None:
            os.environ.pop("DENTALPIN_REPO_ROOT", None)
        else:
            os.environ["DENTALPIN_REPO_ROOT"] = prev_repo_root


def test_dynamic_and_enum_publishers_are_attributed() -> None:
    gen = _load_generator()
    publishers = gen._scan_publishers()

    # (event, expected owning module) — one representative per mechanism.
    expectations = {
        "appointment.completed": "agenda",  # variable dispatch (status map)
        "odontogram.surface.updated": "odontogram",  # module-local enum
        "clinical_notes.diagnosis_created": "clinical_notes",  # note-type map
        "notification.sent": "notifications",  # gateway helper dispatch
    }
    for event, module in expectations.items():
        sites = publishers.get(event)
        assert sites, f"{event} resolved to NO publisher (regex regression)"
        assert module in {m for m, _path, _line in sites}, (
            f"{event} should be attributed to {module}, got {sites}"
        )
