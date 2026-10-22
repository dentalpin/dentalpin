"""API schemas for the module settings registry (ADR 0042)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SettingDeclaration(BaseModel):
    """One declared setting, rendered by the generic settings form."""

    key: str
    type: Literal["string", "integer", "boolean", "enum"]
    default: Any
    writable: bool
    label_key: str
    description_key: str | None = None
    choices: list[str] = Field(default_factory=list)
    min_value: int | None = None
    max_value: int | None = None
    max_length: int | None = None
    multiline: bool = False
    nullable: bool = False


class ModuleSettingsResponse(BaseModel):
    module: str
    settings: list[SettingDeclaration]
    values: dict[str, Any]


class ModuleSettingsUpdate(BaseModel):
    values: dict[str, Any]
