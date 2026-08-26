# 0021 — Cross-module client refresh bus (`useDataBus`)

Date: 2026-08-25 · Status: accepted

## Context

Modules render UI into shared host surfaces (slots, header regions,
dynamic routes). When module A mutates data that module B displays, B
must refetch — but the modular architecture (ADR 0001) forbids B from
importing A's composables or watching its state, and A must not know
who consumes its data. Issue #274 (stale patient warning chips after a
medical-history save) is the concrete case: clinical safety information
went stale until a full page reload.

Server-side, this problem was already solved by ADR 0003 (event bus:
publishers are data owners, subscribers anonymous, transactional).
Client-side there was no equivalent contract.

## Decision

The host shell owns **one** client pub/sub — `useDataBus`
(`frontend/app/composables/useDataBus.ts`) — and it is the sanctioned
cross-module refresh mechanism:

- **Publishers are data owners.** After a successful mutation, the
  owning composable calls `useDataBus().publish('<module-namespace>')`.
  The namespace is the module name — same keying as tool namespaces and
  permission grants.
- **Subscribers are anonymous.** Any component calls
  `useDataBus().on('<namespace>', handler)` to react. No imports from
  other modules, no shared state beyond an opaque tick counter
  (SSR-safe via `useState`, auto-cleaned via `onScopeDispose`).
- **Payload-less by design.** The bus carries a monotonic tick per
  namespace, not event bodies. A subscriber that cannot scope the
  signal simply refetches; one cheap GET self-corrects. If precision
  is ever needed, `publish(namespace, payload?)` can be added without
  breaking existing subscribers.

Precedent: copilot already published ticks after confirmed write tools
and agenda subscribed with `useDataBus().on('agenda', …)`. This ADR
formalizes that usage as *the* mechanism so parallel ad-hoc signals do
not proliferate.

## Alternatives rejected

- **Slot ctx refreshKey**: the host would need to know which mutations
  are "relevant" to each slot consumer — knowledge flowing in the wrong
  direction (data owner → consumer's host integration point).
- **Route/visibility-based refetch**: trivially safe, but does not fix
  the in-page case — which is exactly the clinically important one
  (#274).

## Consequences

- First adopters (#274): `patients_clinical` publishes after
  `saveMedicalHistory`; medical_reference's `PatientReferenceFlagsChips`
  subscribes on `patients_clinical` and refetches its warning chips.
  The data owner subscribes to its own namespace too —
  `usePatientAlerts` had the same staleness bug in the same header line.
  Publishing is not a substitute for subscribing: a module that renders
  its own data into a shared surface is a consumer like any other.
- New cross-module client couplings must use this bus and document the
  namespace pair in both modules' CLAUDE.md.
- The bus stays payload-less unless a demonstrated need appears;
  payload-carrying events belong server-side (ADR 0003), where
  transactions and ordering exist.
