# Copilot: pluggable LLM providers — free & local tiers

> Design brief for issue #332 (design-first, requested by @lamanji).
> Scopes the provider registry, per-clinic configuration, free/local
> tiers and guardrails. No copilot UI behaviour changes. Implementation
> is deliberately NOT started here — this document is the discussion
> artifact the issue asked for.

## Why

`app/core/llm/factory.py` ships OpenAI-only (`SUPPORTED_PROVIDERS =
("openai",)`) while everything above it is already provider-neutral:
the orchestrator speaks `base.py`'s `Provider` protocol (streaming
`complete(system, messages, tools, model, max_tokens)`), neutral
message/event types, and the redactor tokenizes on the way to whatever
provider is configured. The factory's own docstring reserves the slot.
What's missing is purely: more implementations, a way for a clinic to
pick one safely, and a way to evaluate DentalPin without a paid key.

## Provider set (proposal)

| Provider | Tier | Why it's on the list | Protocol notes |
|---|---|---|---|
| OpenAI | paid | current default, unchanged | as today |
| Anthropic | paid | tool-use quality; already name-checked in the factory docstring | native tool-use blocks map 1:1 onto `ToolUseBlock` |
| Google Gemini | paid + free tier | free tier usable for evaluation | function-calling schema differs; adapter owns the mapping |
| OpenRouter | paid, many models | one key, many models — useful for self-hosters comparing | OpenAI-compatible wire format → thin subclass of the OpenAI adapter |
| Groq | free tier | fast free evaluation tier | OpenAI-compatible → same thin subclass |
| Ollama | local, free | the self-hosted answer: no data leaves the machine at all | OpenAI-compatible endpoint (`/v1/chat/completions`); tool-use only on models that support it — see capability flags |

Two structural observations that shrink the work:

1. **Three of the six speak the OpenAI wire format** (OpenRouter,
   Groq, Ollama). One `OpenAICompatibleProvider(base_url, api_key)`
   covers them; the registry entries differ only in defaults and
   capability flags.
2. **Capability flags belong in the registry, not in callers.** Each
   registry entry declares `supports_tools: bool` and
   `redaction_required: bool` (Ollama-local ⇒ `False` — nothing leaves
   the machine, so the cloud-path redaction gate can relax; every
   remote provider ⇒ `True`, non-negotiable). The orchestrator already
   branches on the cloud path for redaction; it reads the flag instead
   of hardcoding "openai ⇒ cloud".

A provider whose model can't do tool-use degrades the copilot from
"agent" to "chat" — that is a worse product, not a smaller one. So:
**tool-use-incapable configurations are rejected at settings-save
time** (422 naming the capability), not silently degraded. For Ollama
this means validating the selected model against the capability probe,
not the provider.

## Registry shape

Mechanically the same pattern as `channel_registry` /
`BillingHookRegistry`, registered from `on_activate()` per ADR 0020
(#325 made that the enforced rule):

```python
@dataclass(frozen=True)
class ProviderSpec:
    name: str                 # "anthropic"
    label: str                # "Anthropic"
    tier: Literal["paid", "free", "local"]
    default_model: str
    supports_tools: bool
    redaction_required: bool
    needs_api_key: bool       # Ollama: False
    factory: Callable[[ProviderConfig], Provider]

llm_provider_registry.register(ProviderSpec(...))
```

`SUPPORTED_PROVIDERS` dies; `get_provider` resolves through the
registry and keeps raising `LLMConfigError` for unknown names so a
clinic can never select what the deployment can't serve.

## Per-clinic configuration

Extends the existing `copilot_settings` (`GET/PATCH /settings`,
`copilot.configure`) rather than inventing a new surface:

- `provider` (registry name), `model`, `base_url` (Ollama/OpenRouter
  self-hosters), and `api_key` — stored **encrypted at rest** with the
  same field-encryption pattern #229 (payroll) establishes; if #229
  hasn't landed first, this issue carries the shared
  `EncryptedString` TypeDecorator and #229 reuses it. The key is
  write-only through the API: `PATCH` accepts it, `GET` returns only
  `has_api_key: bool` (the `whatsapp_kapso` settings precedent).
- Deployment-level env keys (`OPENAI_API_KEY` today) remain the
  fallback when the clinic has none — unchanged self-hosted behaviour.
- Settings-save validates: provider known, model non-empty, key
  present when `needs_api_key`, tool-use capability (above), and a
  **live one-token ping** with the supplied key so a typo'd key fails
  at save time with the provider's own error, not at the first patient
  query. The ping bypasses redaction (it sends no PHI — a static
  probe string).

## Free-tier / demo story

- `tier: "free"` providers (Groq, Gemini free) make the demo and
  first-run evaluation possible without a card. The settings UI
  groups the picker by tier and labels free tiers with their real
  limits (rate/quota copy maintained per provider entry).
- `tier: "local"` (Ollama) is the privacy-first pitch: the settings
  page shows "no data leaves this server" when selected — and the
  redaction flag genuinely relaxes only in this mode.
- **Locality is validated, not assumed** (gotcha flagged by @lamanji
  in review): the redaction relaxation keys off the *resolved
  deployment*, never the provider name alone. At settings-save the
  `base_url` must resolve to loopback / a private RFC-1918 address /
  a same-host socket for the `local` tier to hold; an "Ollama" entry
  pointing at a public endpoint is stored as `tier: "free"`-equivalent
  with `redaction_required: True` and the UI drops the "no data
  leaves this server" copy. A DNS-rebinding-style change after save is
  out of scope for v1 but the check re-runs on every settings read
  that renders the privacy copy.
- The seeded demo clinic stays provider-less: the copilot button
  renders its existing "not configured" state. No fake responses.

## Guardrails

Already present and reused, not rebuilt: per-clinic token budgets and
the per-role `agents.view` gate. Added:

- `max_tokens` per request comes from the `COPILOT_MAX_TOKENS` setting
  (default 4096, forwarded by `docker-compose.yml` and
  `docker-compose.prod.yml`). There is no per-provider ceiling field:
  free-tier caps are the provider's own, and the operator lowers the
  single value if a tier rejects long answers.
- Budget accounting keys on `(clinic, provider)` so switching
  providers doesn't reset spend tracking mid-month.
- Per-role enable stays the existing RBAC surface — no new mechanism.
  (Reading the settings needs `copilot.configure` today; the picker is
  admin-facing, so no #310-style audience-role gap here.)

## Out of scope

- Streaming-protocol changes (`Provider` protocol is already neutral
  and stays byte-identical for OpenAI).
- Multi-provider fallback chains (pick one; fail honestly).
- Fine-tuning, embeddings, or non-copilot LLM consumers.
- The navigation reorg (#232) — kept separate per the issue.

## Suggested slicing (if the design is accepted)

1. Registry + `OpenAICompatibleProvider` + Ollama/Groq/OpenRouter
   entries (small, mostly config).
2. Anthropic + Gemini adapters (real block-mapping work, one each).
3. Settings: encrypted key field + validation ping + tiered picker UI.
4. Docs: copilot CLAUDE.md provider table, self-hosting guide section
   ("run it fully local with Ollama").

Each slice ships alone; 1+3 already deliver the free/local evaluation
story with zero new adapter risk.
