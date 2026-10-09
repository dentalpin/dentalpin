#!/usr/bin/env python3
"""Coverage check for the documentation portal (ADR 0009 / issue #75).

For every module under ``backend/app/modules/<name>/``, verifies that
the documentation contract holds:

- ``docs/technical/<module>/overview.md`` exists.
- ``docs/technical/<module>/permissions.md`` exists when the module
  returns at least one permission from ``get_permissions()``.
- ``docs/technical/<module>/events.md`` exists when the module emits or
  subscribes events.
- Every Nuxt page under ``<module>/frontend/pages/**`` has a matching
  screen file in **both**
  ``docs/user-manual/en/<module>/screens/<slug>.md`` *and*
  ``docs/user-manual/es/<module>/screens/<slug>.md`` with frontmatter
  whose ``route`` field equals the page's route.
- Every screen file's frontmatter ``route`` resolves to a real page,
  ``related_endpoints`` (if present) reference paths that exist on the
  module's router, and ``related_permissions`` (if present) are
  returned by the module's ``get_permissions()`` (with the namespace
  prefix stripped or left as-is).

Default mode is **warning-only** (prints findings, exits 0). The
``--strict`` flag turns violations into an exit code 1 and is what the
backfill PR will switch CI to. Today, the warning-only mode runs in the
existing ``catalog-freshness`` CI job.

Companion to ``backend/scripts/generate_catalogs.py``. Shares its
bootstrap, but does **not** mutate any file.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _locate_repo_root() -> Path:
    """Resolve the repo root.

    Order:

    1. ``DENTALPIN_REPO_ROOT`` env var if set and it holds both ``docs/``
       and ``backend/`` (useful in Docker where ``/app`` is the backend
       mount and ``/docs`` is mounted separately — historically set
       ``DENTALPIN_REPO_ROOT=/`` with ``/docs`` + ``/backend`` available).
       A stale/mis-pointed override is tolerated and skipped rather than
       hard-failing the script (some deploy layouts bind only the backend).
    2. Walk up from this file until we find both ``docs/`` and ``backend/``.
    """
    override = os.environ.get("DENTALPIN_REPO_ROOT")
    if override:
        root = Path(override).resolve()
        if (root / "docs").is_dir() and (root / "backend").is_dir():
            return root
    here = Path(__file__).resolve()
    for candidate in (here.parent, *here.parents):
        if (candidate / "docs").is_dir() and (candidate / "backend").is_dir():
            return candidate
    raise RuntimeError(
        f"Could not locate repo root from {here} "
        f"(DENTALPIN_REPO_ROOT={override!r} is not a valid checkout). "
        "Set DENTALPIN_REPO_ROOT or run the script from a checkout that "
        "contains both `docs/` and `backend/`."
    )


REPO_ROOT = _locate_repo_root()
BACKEND_ROOT = REPO_ROOT / "backend"
MODULES_ROOT = BACKEND_ROOT / "app" / "modules"
DOCS_ROOT = REPO_ROOT / "docs"
TECHNICAL_ROOT = DOCS_ROOT / "technical"
USER_MANUAL_ROOT = DOCS_ROOT / "user-manual"

LOCALES = ("en", "es")


def _bootstrap_env() -> None:
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://stub:stub@localhost:5432/stub",
    )
    os.environ.setdefault("SECRET_KEY", "docs-coverage-stub-key-32chars-minimum")
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("TESTING", "true")
    os.environ.setdefault("DENTALPIN_DEV_MODULE_SCAN", "true")
    sys.path.insert(0, str(BACKEND_ROOT))


_bootstrap_env()

from app.core.plugins.loader import discover_modules  # noqa: E402

# ---------------------------------------------------------------------------
# Tiny YAML frontmatter parser.
#
# We deliberately avoid pulling in PyYAML — the schema is fixed (strings,
# lists of strings) and a regex split is enough. If the contract grows
# nested objects, swap this for `yaml.safe_load`.
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    body = text[3:end].strip("\n")
    out: dict[str, object] = {}
    current_list_key: str | None = None
    for raw in body.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("  - "):
            if current_list_key is None:
                continue
            out.setdefault(current_list_key, [])
            assert isinstance(out[current_list_key], list)
            out[current_list_key].append(raw.removeprefix("  - ").strip())
            continue
        if raw.startswith("- "):  # top-level list — not in our schema
            continue
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            current_list_key = key
            out[key] = []
        else:
            current_list_key = None
            out[key] = _parse_scalar_or_flow_list(value.strip("\"'"))
    return out


def _parse_scalar_or_flow_list(value: str) -> object:
    """Parse a frontmatter scalar that may use YAML flow-list syntax.

    ``related_permissions: []`` must come back as an empty list, not the
    string ``"[]"`` (whose characters were previously iterated as phantom
    permissions ``'['`` and ``']'`` — #543).
    """
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",")]
    return value


# ---------------------------------------------------------------------------
# Module discovery + per-module facts
# ---------------------------------------------------------------------------


@dataclass
class ModuleFacts:
    name: str
    permissions: list[str]
    events_emitted: list[str]
    events_consumed: list[str]
    pages: dict[str, Path]  # route -> .vue path
    endpoints: list[tuple[str, str]]  # (METHOD, full path including /api/v1/<m>)
    has_frontend: bool


HTTP_METHODS = ("get", "post", "put", "patch", "delete")
ROUTER_DECORATOR_RE = re.compile(
    r"@router\.(?P<method>get|post|put|patch|delete)\(\s*[\"'](?P<path>[^\"']*)[\"']",
)
# First arg of an event_bus.publish(...) call. Captures the four shapes a
# module can publish through so the "events.md required" rule below fires
# for enum-based and dynamic publishers too, not just string literals
# (audit S4, #94 — the old regex only had a group for the literal case,
# so EventType.X publishers were invisible and the rule never triggered).
PUBLISH_RE = re.compile(
    r"event_bus\.publish\(\s*(?:"
    r"EventType\.(?P<const>[A-Z_]+)"
    r"|(?P<enum>[A-Z]\w*\.[A-Z_]+)"
    r"|[\"'](?P<lit>[\w.]+)[\"']"
    r"|(?P<var>[a-z_]\w*)"
    r")"
)


def _iter_leaf_routes(router: object, prefix: str) -> object:
    """Yield (methods, full path) descending into deferred includes.

    FastAPI defers nested ``include_router`` entries (``_IncludedRouter``
    placeholders resolve only when the app serves). We descend ourselves
    via the placeholder's sub-router, threading each include's prefix —
    so sub-router prefixes (e.g. a module's ``public_router`` under
    ``/public/...``) compose exactly as in production. The old decorator
    regex missed them entirely (it only matched ``@router.``) — #543.
    """
    for route in getattr(router, "routes", []) or []:
        methods = {m.lower() for m in (getattr(route, "methods", None) or set())}
        path = getattr(route, "path", None)
        if methods and path is not None:
            yield methods, f"{prefix}{path}"
            continue
        if type(route).__name__ == "_IncludedRouter":
            box = getattr(route, "__dict__", {}) or {}
            sub = box.get("original_router")
            extra = getattr(box.get("include_context"), "prefix", "") or ""
            if sub is not None:
                yield from _iter_leaf_routes(sub, f"{prefix}{extra}")


def _walk_router(router: object, mount_prefix: str) -> list[tuple[str, str]]:
    """Return [(METHOD, full path)] for every route a module mount serves."""
    endpoints: list[tuple[str, str]] = []
    for methods, full in _iter_leaf_routes(router, mount_prefix):
        for method in sorted(methods):
            if method in HTTP_METHODS:
                endpoints.append((method.upper(), full))
    return endpoints


def _scan_module_endpoints_regex(mod_dir: Path, mount_prefix: str) -> list[tuple[str, str]]:
    """Fallback decorator scan when a module router cannot be walked live."""
    endpoints: list[tuple[str, str]] = []
    for py_file in mod_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="replace")
        if "@router." not in text:
            continue
        for match in ROUTER_DECORATOR_RE.finditer(text):
            method = match.group("method").upper()
            sub_path = match.group("path") or ""
            full = f"{mount_prefix}{sub_path}".rstrip("/") or mount_prefix
            endpoints.append((method, full))
    return endpoints


def _scan_module_endpoints(
    module: object, mod_dir: Path, mount_prefix: str
) -> list[tuple[str, str]]:
    """Return [(METHOD, '/api/v1/<m>/<path>')] for every mounted route."""
    try:
        router = module.get_router()  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 — exotic routers fall back to the regex scan
        router = None
    if router is not None:
        walked = _walk_router(router, mount_prefix)
        if walked:
            return walked
    return _scan_module_endpoints_regex(mod_dir, mount_prefix)


def _scan_core_endpoints() -> list[tuple[str, str]]:
    """Endpoints mounted outside modules (auth, roles) under ``/api/v1``."""
    endpoints: list[tuple[str, str]] = []
    try:
        from app.core.auth.router import router as auth_router
        from app.core.auth.router_roles import router as roles_router
    except Exception:  # noqa: BLE001 — core routers unavailable; modules only
        return endpoints
    endpoints.extend(_walk_router(auth_router, "/api/v1"))
    endpoints.extend(_walk_router(roles_router, "/api/v1"))
    return endpoints


def _scan_module_publishers(mod_dir: Path) -> set[str]:
    """Best-effort grep of event_bus.publish callsites in the module."""
    out: set[str] = set()
    for py_file in mod_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="replace")
        if "event_bus.publish" not in text:
            continue
        for match in PUBLISH_RE.finditer(text):
            token = (
                match.group("const")
                or match.group("lit")
                or match.group("enum")
                or match.group("var")
            )
            if token:
                out.add(token)
    return out


def _page_to_route(rel: Path) -> str:
    """Convert pages/foo/[id].vue → /foo/[id], pages/foo/index.vue → /foo."""
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "index":
        parts.pop()
    return "/" + "/".join(parts) if parts else "/"


def _scan_module_pages(mod_dir: Path) -> dict[str, Path]:
    pages_dir = mod_dir / "frontend" / "pages"
    out: dict[str, Path] = {}
    if not pages_dir.is_dir():
        return out
    for vue in pages_dir.rglob("*.vue"):
        rel = vue.relative_to(pages_dir)
        route = _page_to_route(rel)
        out[route] = vue
    return out


def _collect_facts(module) -> ModuleFacts:
    name = module.name
    mod_dir = MODULES_ROOT / name
    permissions = list(getattr(module, "get_permissions", lambda: [])() or [])
    handlers = getattr(module, "get_event_handlers", lambda: {})() or {}
    events_consumed = sorted(handlers.keys())
    events_emitted = sorted(_scan_module_publishers(mod_dir))
    pages = _scan_module_pages(mod_dir)
    endpoints = _scan_module_endpoints(module, mod_dir, mount_prefix=f"/api/v1/{name}")
    has_frontend = (mod_dir / "frontend").is_dir()
    return ModuleFacts(
        name=name,
        permissions=permissions,
        events_emitted=events_emitted,
        events_consumed=events_consumed,
        pages=pages,
        endpoints=endpoints,
        has_frontend=has_frontend,
    )


# ---------------------------------------------------------------------------
# Screen MD discovery
# ---------------------------------------------------------------------------


@dataclass
class ScreenDoc:
    locale: str  # 'en' | 'es'
    module: str
    path: Path
    frontmatter: dict[str, object]


def _collect_screens(module: str) -> dict[str, list[ScreenDoc]]:
    """{locale: [ScreenDoc, ...]} for every screen MD found for this module."""
    out: dict[str, list[ScreenDoc]] = {loc: [] for loc in LOCALES}
    for locale in LOCALES:
        screens_dir = USER_MANUAL_ROOT / locale / module / "screens"
        if not screens_dir.is_dir():
            continue
        for md in sorted(screens_dir.glob("*.md")):
            text = md.read_text(encoding="utf-8", errors="replace")
            fm = _parse_frontmatter(text)
            out[locale].append(ScreenDoc(locale=locale, module=module, path=md, frontmatter=fm))
    return out


# ---------------------------------------------------------------------------
# The actual checks
# ---------------------------------------------------------------------------


@dataclass
class Findings:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def ok(self) -> bool:
        return not self.errors and not self.warnings


def _normalise_endpoint(method: str, path: str) -> str:
    """`{patient_id}` and `:patient_id` and `[id]` all collapse to `<param>`."""
    path = path.split("?", 1)[0]  # docs may carry example query strings
    norm = re.sub(r"\{[^}]+\}", "<param>", path)
    norm = re.sub(r":[a-zA-Z_][\w]*", "<param>", norm)
    norm = re.sub(r"\[[^\]]+\]", "<param>", norm)
    return f"{method.upper()} {norm.rstrip('/') or '/'}"


def _check_module(
    facts: ModuleFacts,
    findings: Findings,
    all_endpoints: set[tuple[str, str]],
    bare_permissions: set[str],
    qualified_permissions: set[str],
) -> None:
    name = facts.name
    tech_dir = TECHNICAL_ROOT / name

    # 1. technical/overview.md
    if not (tech_dir / "overview.md").is_file():
        findings.err(
            f"{name}: missing docs/technical/{name}/overview.md "
            "(every module needs a technical overview)."
        )

    # 2. technical/permissions.md when permissions exist
    if facts.permissions and not (tech_dir / "permissions.md").is_file():
        findings.err(
            f"{name}: get_permissions() returns {facts.permissions!r} "
            f"but docs/technical/{name}/permissions.md is missing."
        )

    # 3. technical/events.md when events flow either way
    if (facts.events_emitted or facts.events_consumed) and not (tech_dir / "events.md").is_file():
        findings.err(
            f"{name}: emits/subscribes events "
            f"(emit={facts.events_emitted}, sub={facts.events_consumed}) "
            f"but docs/technical/{name}/events.md is missing."
        )

    # 4. Per-screen coverage in BOTH locales.
    screens_by_locale = _collect_screens(name)
    routes_by_locale = {
        locale: {str(s.frontmatter.get("route") or ""): s for s in docs}
        for locale, docs in screens_by_locale.items()
    }

    for route, page_path in sorted(facts.pages.items()):
        for locale in LOCALES:
            if route not in routes_by_locale[locale]:
                findings.err(
                    f"{name}: page {page_path.relative_to(REPO_ROOT)} "
                    f"(route {route}) has no screen file under "
                    f"docs/user-manual/{locale}/{name}/screens/ "
                    f"(frontmatter route: {route})."
                )

    # 5. Validate every screen MD frontmatter.
    # The portal contract resolves related_endpoints against ANY registered
    # endpoint (screens call other modules' APIs), not just this module's
    # router — #543. Same for related_permissions (bare action names).
    valid_endpoints = {_normalise_endpoint(m, p) for m, p in all_endpoints}
    for locale, docs in screens_by_locale.items():
        for screen in docs:
            fm = screen.frontmatter
            rel = screen.path.relative_to(REPO_ROOT)
            if "module" not in fm or fm["module"] != name:
                findings.err(
                    f"{rel}: frontmatter `module` must equal '{name}' (found {fm.get('module')!r})."
                )
            route = str(fm.get("route") or "")
            if not route:
                findings.err(f"{rel}: frontmatter `route` is required.")
            elif route not in facts.pages:
                findings.warn(
                    f"{rel}: frontmatter route {route!r} does not match any "
                    f"page under {name}/frontend/pages/ "
                    f"(known: {sorted(facts.pages.keys())})."
                )
            if not fm.get("last_verified_commit"):
                findings.warn(f"{rel}: frontmatter `last_verified_commit` is empty.")

            for ep in fm.get("related_endpoints", []) or []:
                m = re.match(r"\s*([A-Z]+)\s+(.+)\s*$", str(ep))
                if not m:
                    findings.err(
                        f"{rel}: malformed related_endpoint {ep!r} (expected 'METHOD /path')."
                    )
                    continue
                method, path = m.group(1), m.group(2).strip()
                key = _normalise_endpoint(method, path)
                if key not in valid_endpoints:
                    findings.err(
                        f"{rel}: related_endpoint {method} {path} is not "
                        f"a registered endpoint (after normalising path params)."
                    )

            for perm in fm.get("related_permissions", []) or []:
                # Accept 'module.resource.action', bare 'resource.action',
                # and bare 'action' (stripped to the last two segments).
                text = str(perm)
                bare = text.split(".", 1)[-1]
                short = ".".join(text.split(".")[-2:])
                if (
                    text not in qualified_permissions
                    and text not in bare_permissions
                    and bare not in bare_permissions
                    and short not in bare_permissions
                ):
                    findings.err(
                        f"{rel}: related_permission {perm!r} is not a registered permission."
                    )


def _check_locale_parity(findings: Findings, root: Path | None = None) -> None:
    """EN and ES must ship the same .md file set — same relative paths.

    The slug is the identity of a page across locales (CLAUDE.md's
    "create both en/… and es/…" rule). A file present on one side only
    is either a missing translation or a slug translated by mistake —
    both drifts CI never caught before (#128).
    """
    root = USER_MANUAL_ROOT if root is None else root
    files_by_locale: dict[str, set[str]] = {}
    for locale in LOCALES:
        loc_root = root / locale
        files_by_locale[locale] = (
            {p.relative_to(loc_root).as_posix() for p in loc_root.rglob("*.md")}
            if loc_root.is_dir()
            else set()
        )
    en_files, es_files = files_by_locale["en"], files_by_locale["es"]
    for rel in sorted(en_files - es_files):
        findings.err(
            f"docs/user-manual/en/{rel}: has no ES counterpart at "
            f"docs/user-manual/es/{rel} (translate it, or rename a "
            f"mistranslated slug — slugs must match across locales)."
        )
    for rel in sorted(es_files - en_files):
        findings.err(
            f"docs/user-manual/es/{rel}: has no EN counterpart at "
            f"docs/user-manual/en/{rel} (translate it, or rename a "
            f"mistranslated slug — slugs must match across locales)."
        )


def _check_orphan_screens(modules: list[str], findings: Findings) -> None:
    """Find screen MDs whose module folder doesn't exist."""
    known = set(modules)
    for locale in LOCALES:
        loc_root = USER_MANUAL_ROOT / locale
        if not loc_root.is_dir():
            continue
        for module_dir in loc_root.iterdir():
            if not module_dir.is_dir():
                continue
            if module_dir.name in {"screens"}:
                continue  # not a module folder
            if module_dir.name not in known:
                findings.warn(
                    f"docs/user-manual/{locale}/{module_dir.name}/: "
                    f"no module called '{module_dir.name}' is loaded."
                )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def run(strict: bool) -> int:
    findings = Findings()

    modules = list(discover_modules())
    if not modules:
        findings.err(
            "No modules discovered. Ensure DENTALPIN_DEV_MODULE_SCAN=true and "
            "the backend is installed."
        )

    facts_by_name = {m.name: _collect_facts(m) for m in modules}
    all_endpoints = {(m, p) for facts in facts_by_name.values() for m, p in facts.endpoints}
    all_endpoints.update(_scan_core_endpoints())
    bare_permissions = {perm for facts in facts_by_name.values() for perm in facts.permissions}
    qualified_permissions = {
        f"{name}.{perm}" for name, facts in facts_by_name.items() for perm in facts.permissions
    }
    for facts in facts_by_name.values():
        _check_module(facts, findings, all_endpoints, bare_permissions, qualified_permissions)

    _check_orphan_screens([m.name for m in modules], findings)
    _check_locale_parity(findings)

    if findings.warnings:
        print("Documentation coverage warnings:", file=sys.stderr)
        for w in findings.warnings:
            print(f"  ⚠  {w}", file=sys.stderr)
    if findings.errors:
        print("Documentation coverage errors:", file=sys.stderr)
        for e in findings.errors:
            print(f"  ✗  {e}", file=sys.stderr)

    if findings.ok():
        print("docs coverage OK.")
        return 0

    if strict:
        if findings.errors:
            print(
                f"\nFAILED in --strict mode "
                f"({len(findings.errors)} error(s), {len(findings.warnings)} warning(s)).",
                file=sys.stderr,
            )
            return 1
        print(
            f"\nPASS in --strict mode "
            f"(0 error(s), {len(findings.warnings)} informational warning(s)).",
            file=sys.stderr,
        )
        return 0

    print(
        f"\n(warning-only mode — backfill in progress, "
        f"{len(findings.errors)} error(s) treated as warnings, "
        f"{len(findings.warnings)} warning(s)).",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on any violation. Default: warning-only.",
    )
    args = parser.parse_args()
    return run(strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
