"""PHI redaction boundary for the agentic layer.

No patient identifier leaves the server in cleartext toward a cloud LLM.
A per-session :class:`SymbolTable` maps real values to stable opaque
tokens (``NAME_a1b2c3``, ``PHONE_…``, ``PATIENT_…``); outgoing payloads
are tokenized, assistant output and tool-call arguments are rehydrated.

Tokens are **deterministic per conversation**: a salted hash of the
real value, so the same value always maps to the same token *within*
one conversation. That lets a resumed turn rebuild an equivalent table
by re-redacting the loaded history — tokens the model emitted in an
earlier request still restore. The salt is per-conversation and stored
server-side (never in the context blob or logs), so the same patient
yields unrelated tokens across conversations and no global dictionary
attack applies (#586).

v1 scope (see ``docs/technical/copilot-agentic-architecture.md`` §2.3):

* structured tool inputs/results — key-based redaction over the JSON;
* seeded context entities — pre-loaded at session start;
* user free text — substring replacement of entities *already* in the
  table. **Known gap:** a name the user types for an entity not yet
  loaded cannot be caught without NER. Tools that return free prose set
  ``Tool.exposes_free_text=True`` and are excluded from the cloud path
  by the orchestrator while redaction is enabled.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.llm.base import (
    ContentBlock,
    ProviderMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

# key (lower-cased) -> token kind
_NAME_KEYS = {"first_name", "last_name", "full_name", "name", "patient_name"}
_PHONE_KEYS = {"phone", "mobile", "telephone", "phone_number"}
_EMAIL_KEYS = {"email", "email_address"}
_NATIONAL_ID_KEYS = {"dni", "nif", "tax_id", "national_id"}
_DOB_KEYS = {"date_of_birth", "dob", "birth_date"}
# UUID-valued reference keys -> kind
_ID_KIND = {
    "id": "REF",
    "patient_id": "PATIENT",
    "appointment_id": "APPT",
}

_KIND_FOR_KEY: dict[str, str] = {}
for _k in _NAME_KEYS:
    _KIND_FOR_KEY[_k] = "NAME"
for _k in _PHONE_KEYS:
    _KIND_FOR_KEY[_k] = "PHONE"
for _k in _EMAIL_KEYS:
    _KIND_FOR_KEY[_k] = "EMAIL"
for _k in _NATIONAL_ID_KEYS:
    _KIND_FOR_KEY[_k] = "NATID"
for _k in _DOB_KEYS:
    _KIND_FOR_KEY[_k] = "DOB"

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


# 48-bit tokens: birthday collisions stay negligible inside one
# conversation, unlike the old 24-bit form (#586).
_TOKEN_HEX_CHARS = 12


def _token_for(real: str, kind: str, salt: str | None = None) -> str:
    material = f"{salt}:{real}" if salt else real
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:_TOKEN_HEX_CHARS]
    return f"{kind}_{digest}"


@dataclass
class SymbolTable:
    """Bidirectional map between real values and per-conversation tokens.

    ``salt`` must be the owning conversation's persisted salt. ``None``
    reproduces the legacy unsalted scheme and exists for unit tests
    only — production paths always pass a real salt.
    """

    salt: str | None = None
    _to_token: dict[str, str] = field(default_factory=dict)
    _to_real: dict[str, str] = field(default_factory=dict)

    def tokenize(self, real: str, kind: str) -> str:
        token = self._to_token.get(real)
        if token is None:
            token = _token_for(real, kind, self.salt)
            self._to_token[real] = token
            self._to_real[token] = real
        return token

    def restore_text(self, text: str) -> str:
        if not text or not self._to_real:
            return text
        # Replace longest tokens first to avoid prefix collisions.
        for token in sorted(self._to_real, key=len, reverse=True):
            if token in text:
                text = text.replace(token, self._to_real[token])
        return text

    def replace_known(self, text: str) -> str:
        """Tokenize occurrences of already-known real values in free text."""
        if not text or not self._to_token:
            return text
        for real in sorted(self._to_token, key=len, reverse=True):
            if real and real in text:
                text = text.replace(real, self._to_token[real])
        return text


class Redactor:
    """Applies the redaction boundary over neutral messages and JSON.

    When ``enabled`` is ``False`` every method is the identity — useful
    for tests and the (deferred) self-hosted path where data never
    leaves the clinic.
    """

    def __init__(self, *, enabled: bool = True, salt: str | None = None) -> None:
        self.enabled = enabled
        self.table = SymbolTable(salt=salt)

    # --- seeding --------------------------------------------------------

    def seed(self, context: dict[str, Any] | None) -> None:
        """Pre-load known entities from a conversation's context blob."""
        if not self.enabled or not context:
            return
        self._redact_obj(dict(context))  # populates the table as a side-effect

    # --- outgoing (server -> provider) ---------------------------------

    def redact_outgoing(self, messages: list[ProviderMessage]) -> list[ProviderMessage]:
        """Return a tokenized copy of ``messages``; never mutates input."""
        if not self.enabled:
            return messages
        return [self._redact_message(m) for m in messages]

    def _redact_message(self, msg: ProviderMessage) -> ProviderMessage:
        new_content: list[ContentBlock] = []
        for block in msg.content:
            if isinstance(block, TextBlock):
                new_content.append(TextBlock(self.table.replace_known(block.text)))
            elif isinstance(block, ToolUseBlock):
                new_content.append(
                    ToolUseBlock(block.id, block.name, self._redact_obj(block.input))
                )
            elif isinstance(block, ToolResultBlock):
                new_content.append(
                    ToolResultBlock(
                        block.tool_call_id,
                        self._redact_obj(block.content),
                        block.is_error,
                    )
                )
        return ProviderMessage(role=msg.role, content=new_content)

    def redact_result(self, content: Any) -> Any:
        """Tokenize a single tool result before it is fed back / streamed."""
        if not self.enabled:
            return content
        return self._redact_obj(content)

    def _redact_obj(self, obj: Any, key: str | None = None) -> Any:
        if isinstance(obj, dict):
            return {k: self._redact_obj(v, k) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._redact_obj(v, key) for v in obj]
        if isinstance(obj, str):
            return self._redact_scalar(key, obj)
        return obj

    def _redact_scalar(self, key: str | None, value: str) -> str:
        if not value:
            return value
        lkey = (key or "").lower()
        kind = _KIND_FOR_KEY.get(lkey)
        if kind is not None:
            return self.table.tokenize(value, kind)
        if lkey in _ID_KIND and _UUID_RE.match(value):
            return self.table.tokenize(value, _ID_KIND[lkey])
        return value

    # --- incoming (provider -> server / display) -----------------------

    def rehydrate(self, text: str) -> str:
        """Restore tokens to real values for display."""
        if not self.enabled:
            return text
        return self.table.restore_text(text)

    def resolve_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Restore tokens inside model-produced tool arguments before exec."""
        if not self.enabled:
            return args
        return self._restore_obj(args)

    def _restore_obj(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._restore_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._restore_obj(v) for v in obj]
        if isinstance(obj, str):
            return self.table.restore_text(obj)
        return obj
