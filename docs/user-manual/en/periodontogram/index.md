---
module: periodontogram
last_verified_commit: 84c03fa4
---

# Periodontogram

The **periodontogram** module adds SEPA-standard periodontal charting
and longitudinal tracking to the patient clinical record. It lives
as a sub-tab inside the **Diagnosis** mode, next to the odontogram.
Each exam is stored as a dated, immutable snapshot, which makes
inter-session comparison straightforward.

It is an **optional** module — it does not install automatically.
Activate it from *Admin → Modules → Periodontogram → Install*.

## Screens

- [Periodontogram view](../patients/screens/detail.md#periodontogram) - SEPA
  exam, cell-level editing, indices banner, history slider. It is a
  sub-view of the patient detail page and is documented as a section
  of that page.

## What each exam captures

Per tooth (permanent dentition only, FDI 11–48):

- Implant flag (pre-filled from the odontogram).
- Miller mobility (0–3).
- Individual prognosis (good / fair / poor / hopeless).
- Buccal and lingual / palatal furcation grade (0 / I / II / III) —
  molars only.
- Keratinized gingiva width (mm).

Per site (six sites per tooth: MV, V, DV, ML, L, DL):

- Probing depth (0–15 mm).
- Gingival margin (-5 to +10 mm, negative = overgrowth).
- Bleeding on probing (yes / no).
- Visible plaque (yes / no).
- Suppuration (yes / no).

## Indices computed on close

| Index | Definition |
|-------|------------|
| BoP % | % of measured sites with bleeding on probing. |
| PI % | % of measured sites with plaque. |
| Mean CAL | Mean clinical attachment level (probing + margin). |
| Pockets ≥ 5 mm | Distinct teeth with at least one site ≥ 5 mm. |

Indices are computed automatically and frozen on the snapshot at
close time. They show in the banner above the chart.

## Typical workflow

1. **Open session** from the *Periodontogram* sub-tab. The system
   creates a draft (status `draft`) and pre-fills missing teeth +
   implants by reading the patient's odontogram.
2. **Capture data** by clicking any cell. Edits autosave after
   600 ms; the bottom bar shows the state (Saving… / Pending
   changes / Saved).
3. **Close session** from the sticky bottom action bar. Before
   close, the system flushes any pending edits; upon confirm the
   indices are computed and the snapshot becomes immutable.
4. **Browse history** with the top slider: each node is a closed
   snapshot. The amber banner warns when you are viewing a past
   session.

## Known limitations

- **Permanent dentition only.** Deciduous teeth (51–85) are out of
  scope for SEPA periodontal charting.
- **Closed sessions are not editable.** Corrections require a new
  session.
- **Small screens.** The full SEPA layout needs at least 1024 px of
  width. On vertical tablets and phones it falls back to horizontal
  scroll — a quadrant-by-quadrant swipe layout is planned for a
  later phase.

## Permissions

| Role | Access |
|------|--------|
| admin / dentist | Full. |
| hygienist | Create, edit and close sessions. |
| assistant | Read-only. |
| receptionist | Sub-tab is hidden. |
