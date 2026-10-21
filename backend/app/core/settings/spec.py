"""Declarative clinic setting specs (ADR 0041)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

SettingType = Literal["string", "integer", "boolean", "enum"]
SettingScope = Literal["clinic", "device"]

SETTING_TYPES: tuple[str, ...] = ("string", "integer", "boolean", "enum")
SUPPORTED_SCOPES: tuple[str, ...] = ("clinic",)

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class SettingDeclarationError(ValueError):
    """Raised when a module declares an invalid setting."""


class SettingValueError(ValueError):
    """Raised when a value does not match its declaration."""

    def __init__(self, key: str, reason: str) -> None:
        super().__init__(f"Invalid value for setting '{key}': {reason}")
        self.key = key


@dataclass(frozen=True)
class SettingSpec:
    """One clinic-scoped setting declared by a module.

    ``key`` is module-local: the storage namespace is the module's
    ``manifest["name"]``. ``permission`` gates reading the value and its
    declaration through the generic settings API; ``write_permission``
    (defaulting to ``permission``) gates writes. That is not a confidentiality
    boundary: the namespace lives in ``clinics.settings``, which
    ``GET /api/v1/auth/clinics`` returns to every member of the clinic as
    ``ClinicMetadataResponse.settings``. Never declare secrets.
    """

    key: str
    type: SettingType
    default: Any
    permission: str
    label_key: str
    scope: SettingScope = "clinic"
    write_permission: str | None = None
    description_key: str | None = None
    choices: tuple[str, ...] = ()
    min_value: int | None = None
    max_value: int | None = None
    max_length: int | None = None
    multiline: bool = False
    nullable: bool = False

    @property
    def effective_write_permission(self) -> str:
        return self.write_permission or self.permission


def _check_permission(
    module_name: str,
    permission: str | None,
    field: str,
    known_permissions: set[str] | None,
) -> None:
    if not permission:
        raise SettingDeclarationError(f"{field} is required")
    if not permission.startswith(f"{module_name}."):
        raise SettingDeclarationError(
            f"{field} '{permission}' must be namespaced under '{module_name}.'"
        )
    if known_permissions is not None and permission not in known_permissions:
        raise SettingDeclarationError(
            f"{field} '{permission}' is not one of the module's declared permissions"
        )


def _check_default(spec: SettingSpec) -> None:
    if spec.default is None:
        if not spec.nullable:
            raise SettingDeclarationError(f"'{spec.key}' default is null but nullable is False")
        return
    try:
        validate_value(spec, spec.default)
    except SettingValueError as exc:
        raise SettingDeclarationError(f"'{spec.key}' has an invalid default: {exc}") from exc


def validate_declarations(
    module_name: str,
    specs: list[SettingSpec],
    known_permissions: set[str] | None = None,
) -> None:
    """Validate a module's declarations; raises on the first problem.

    ``known_permissions`` is the module's fully qualified permission set.
    When provided, every declaration permission must be one of them.
    """
    seen: set[str] = set()
    for spec in specs:
        if not isinstance(spec, SettingSpec):
            raise SettingDeclarationError(
                f"'{module_name}' declares a non-SettingSpec entry: {spec!r}"
            )
        if not _KEY_RE.match(spec.key):
            raise SettingDeclarationError(f"'{module_name}' declares an invalid key '{spec.key}'")
        if spec.key in seen:
            raise SettingDeclarationError(f"'{module_name}' declares duplicate key '{spec.key}'")
        seen.add(spec.key)

        if spec.type not in SETTING_TYPES:
            raise SettingDeclarationError(f"'{spec.key}' has unsupported type '{spec.type}'")
        if spec.scope not in SUPPORTED_SCOPES:
            raise SettingDeclarationError(
                f"'{spec.key}' requests scope '{spec.scope}', only 'clinic' is supported"
            )
        _check_permission(
            module_name,
            spec.permission,
            f"'{spec.key}' permission",
            known_permissions,
        )
        if spec.write_permission is not None:
            _check_permission(
                module_name,
                spec.write_permission,
                f"'{spec.key}' write_permission",
                known_permissions,
            )
        if not spec.label_key:
            raise SettingDeclarationError(f"'{spec.key}' is missing label_key")

        if spec.type == "enum":
            if not spec.choices:
                raise SettingDeclarationError(f"'{spec.key}' is an enum without choices")
            if any(not isinstance(choice, str) for choice in spec.choices):
                raise SettingDeclarationError(f"'{spec.key}' choices must be strings")
            if spec.default is not None and spec.default not in spec.choices:
                raise SettingDeclarationError(f"'{spec.key}' default is not one of its choices")
        elif spec.choices:
            raise SettingDeclarationError(f"'{spec.key}' declares choices but is not an enum")

        if spec.type == "integer":
            for bound, value in (("min_value", spec.min_value), ("max_value", spec.max_value)):
                if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                    raise SettingDeclarationError(f"'{spec.key}' {bound} must be an integer")
            if (
                spec.min_value is not None
                and spec.max_value is not None
                and spec.min_value > spec.max_value
            ):
                raise SettingDeclarationError(f"'{spec.key}' min_value exceeds max_value")
        elif spec.min_value is not None or spec.max_value is not None:
            raise SettingDeclarationError(f"'{spec.key}' bounds only apply to integer settings")

        if spec.type == "string":
            if spec.max_length is not None and (
                isinstance(spec.max_length, bool)
                or not isinstance(spec.max_length, int)
                or spec.max_length <= 0
            ):
                raise SettingDeclarationError(f"'{spec.key}' max_length must be a positive integer")
        elif spec.max_length is not None or spec.multiline:
            raise SettingDeclarationError(
                f"'{spec.key}' max_length/multiline only apply to string settings"
            )

        _check_default(spec)


def validate_value(spec: SettingSpec, value: Any) -> Any:
    """Return ``value`` when it matches ``spec``, else raise SettingValueError."""
    if value is None:
        if spec.nullable:
            return None
        raise SettingValueError(spec.key, "must not be null")

    if spec.type == "boolean":
        if not isinstance(value, bool):
            raise SettingValueError(spec.key, "must be a boolean")
    elif spec.type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SettingValueError(spec.key, "must be an integer")
        if spec.min_value is not None and value < spec.min_value:
            raise SettingValueError(spec.key, f"must be >= {spec.min_value}")
        if spec.max_value is not None and value > spec.max_value:
            raise SettingValueError(spec.key, f"must be <= {spec.max_value}")
    elif spec.type == "string":
        if not isinstance(value, str):
            raise SettingValueError(spec.key, "must be a string")
        if spec.max_length is not None and len(value) > spec.max_length:
            raise SettingValueError(spec.key, f"must be at most {spec.max_length} characters")
    elif spec.type == "enum":
        if not isinstance(value, str) or value not in spec.choices:
            raise SettingValueError(spec.key, f"must be one of: {', '.join(spec.choices)}")
    return value
