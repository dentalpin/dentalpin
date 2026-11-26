# Patient timeline module

Unified per-patient activity log. The **firehose subscriber** — listens
to ~22 events across the system to build a single chronological feed.

## Public API

Routes mounted at `/api/v1/patient_timeline/`.

## Dependencies

`manifest.depends = ["patients"]`. Despite consuming events from many
modules, the only **hard** dependency is `patients` (the entity it
indexes). Other event sources are runtime-optional — when a producing
module is uninstalled, this module simply stops receiving its events.

## Permissions

`patient_timeline.read`.

## Tools exposed

Agent tool in `tools.py` (wraps `TimelineService`, no logic duplicated).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `get_patient_timeline` | READ | `TimelineService.get_timeline` | `patient_timeline.read` |

Returns structured event metadata only (type/category/title/timestamp);
the free-text `description` + `event_data` are omitted so no
un-redactable prose reaches the cloud LLM.

## Events emitted

None.

## Events consumed

22 events: appointment lifecycle, budget lifecycle, invoice lifecycle,
treatment_plan lifecycle, odontogram, documents, email, medical
updates. See `docs/events-catalog.md` for the full list.

## Lifecycle

- `removable=False` today, but a strong candidate for `removable=True`
  in the future — the module is purely a derived view.

## Gotchas

- **GDPR erasure: the feed is retained, never rewritten.**
  `erasure.PatientTimelineErasureContributor` is pulled by `gdpr` inside
  the erasure transaction (ADR 0038, #657) and writes nothing: it owns the
  `patient_timeline` coverage scope and reports `retained` under
  Art. 17(3)(b). `title`/`description`/`event_data` are free-form, so all
  three erasure categories are declared. Don't add a redaction pass here
  without a decision on the record — the feed's value is that it is
  append-only.

- **Append-only.** Timeline entries are never edited or deleted, only
  archived. Reactions to delete events log a "removed" entry rather
  than deleting the original.
- **Event handlers must be cheap and idempotent.** The same event can
  arrive twice; deduplicate by `(event_type, source_id)`.
- **Titles are stored in Spanish, shown in the viewer's language (#1174).**
  The UI rebuilds each heading from `event_type` + `event_data`
  (`frontend/utils/timelineTitle.ts`, keys `patients.timeline.titles.*` in
  every host locale) and falls back to the stored `title`. When a handler
  puts a dynamic value in its title (a name, number or subject), put the same
  value in `event_data` too, and add a case plus keys for any new event type.
- **No upstream coupling.** Don't import any of the producing modules'
  services. The whole point of this module is that it's loosely
  coupled to everyone.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md` — the canonical
  example of the event bus paying off.

## CHANGELOG

See `./CHANGELOG.md`.
