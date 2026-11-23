# Dentum Design System

This document is the **single source of truth** for visual design in Dentum. It defines tokens, components and patterns that any contributor (human or agent) must follow when adding or modifying UI.

Dentum is clinical software used by dentists, hygienists, assistants and receptionists for **8+ hour shifts**. The design system optimises for **calm, legibility and clinical safety** in that order. Aesthetics serve those goals — they never override them.

> **Companion docs**
> - Implementation plan: `docs/technical/ui-redesign-calm.md`
> - Module / feature UX briefs: `docs/features/*.md`
> - Module / feature tech plans: `docs/technical/*.md`

---

## 1. Principles

These are ordered. When two principles conflict, the higher one wins.

1. **Clinical signal is sacred — but calm.** Alerts, statuses and patient-critical data are always identifiable, with WCAG AA contrast or better. They render in a **pastel pattern** (soft tinted background + bold semantic text + saturated icon and accent rail), not as walls of saturated colour. The signal is preserved through the icon, the rail and the text colour; the fill is calm.
2. **Calm by subtraction.** Remove a border, a shadow or a saturated background before adding one. The interface should disappear so clinical content can breathe.
3. **One saturated chrome colour.** The default is primary blue; users may choose a calm mint, lavender or coral accent. All semantic colours (success, info, warning, danger) remain independent and render in *soft* variants by default. Saturated `accent` colour is reserved for icons, 2–3 px rails, 1 px borders and destructive action buttons — never for large fills.
4. **Adjustable density.** Comfortable for forms and reading; compact for dense clinical surfaces (odontogram, calendar, treatment lists). User-controlled, persisted.
5. **Vertical rhythm: generous between blocks, denser within.** Cards don't drown in interior padding, but they sit in space.
6. **Motion is meaningful or absent.** Transitions ≤150 ms, only on state change (hover, expand, focus). No decorative animation. Respect `prefers-reduced-motion`.
7. **Warm neutrals, never blue-grey.** Greys carry yellow-brown undertones in both light and dark modes. Reduces visual fatigue across long shifts.
8. **Readability is non-negotiable.** WCAG AA minimum, AAA where it costs nothing. Clinically distinguishable glyphs (`1`/`l`/`I`, `0`/`O`) via Inter's `cv11` feature. Tabular numerals for amounts, doses, times and FDI tooth numbers.

---

## 2. Colour System

All colours are exposed as CSS custom properties on `:root` (light) and `.dark` (dark). Components reference them via Tailwind classes (Nuxt UI 4) or directly via `var(--token)`. **Never** hardcode hex in components.

### 2.1 Surfaces and text — Light mode

| Token | Value | Role |
|---|---|---|
| `--color-canvas` | `#FBFAF8` | Page background (warm off-white) |
| `--color-surface` | `#FFFFFF` | Cards, modals, popovers |
| `--color-surface-muted` | `#F4F2EF` | Alternating rows, sidebar, grouped sections |
| `--color-surface-sunken` | `#EFEDE9` | Inputs, code blocks, inactive areas |
| `--color-border-subtle` | `rgba(15, 17, 22, 0.06)` | Dividers between rows |
| `--color-border` | `rgba(15, 17, 22, 0.10)` | Card borders, input borders |
| `--color-border-strong` | `rgba(15, 17, 22, 0.16)` | Hover borders, soft focus |
| `--color-text` | `rgba(15, 17, 22, 0.92)` | Body and headings |
| `--color-text-muted` | `#615D59` | Secondary text, descriptions |
| `--color-text-subtle` | `#94908A` | Placeholders, metadata |
| `--color-text-disabled` | `#BAB6B0` | Disabled states |

### 2.2 Surfaces and text — Dark mode

Inspired by Linear/Height. Surfaces get **lighter as elevation increases** (the inverse of light mode). This communicates depth without shadows, which barely register in dark UIs. Surfaces are warm dark, not blue-black.

| Token | Value | Role |
|---|---|---|
| `--color-canvas` | `#161513` | Page background |
| `--color-surface` | `#1E1C19` | Cards, modals, sidebar |
| `--color-surface-muted` | `#252320` | Alternating rows |
| `--color-surface-sunken` | `#121110` | Inputs, inactive areas |
| `--color-border-subtle` | `rgba(255, 250, 240, 0.06)` | Dividers |
| `--color-border` | `rgba(255, 250, 240, 0.10)` | Borders |
| `--color-border-strong` | `rgba(255, 250, 240, 0.18)` | Hover, soft focus |
| `--color-text` | `rgba(255, 250, 240, 0.92)` | Body |
| `--color-text-muted` | `#A39E97` | Secondary |
| `--color-text-subtle` | `#787570` | Placeholder |
| `--color-text-disabled` | `#525049` | Disabled |

### 2.3 Primary

The default palette uses Dentum clinical blue (`#00A7EF`) as the canonical primary in light mode and a lighter blue in dark mode. Users can select one of four accent palettes from the app toolbar; the chosen accent is stored per browser and remains independent from light/dark mode. Semantic colors do not change with the selected accent.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--color-primary` | `#00A7EF` | `#42C2FF` | Primary CTAs, links, selection rings |
| `--color-primary-hover` | `#0089C6` | `#8AD9FF` | Hover state |
| `--color-primary-soft` | `#E3F7FF` | `rgba(66,194,255,0.12)` | Active nav pill, highlight backgrounds |
| `--color-primary-soft-text` | `#00658F` | `#8AD9FF` | Text on `--color-primary-soft` |
| `--color-primary-accent` | `#007FAF` | `#42C2FF` | Accent icons and focus treatments |

### 2.3.1 User-selectable accents

| Palette | Light primary | Dark primary | Soft treatment |
|---|---|---|---|
| Clinical blue (default) | `#00A7EF` | `#42C2FF` | Dentum blue |
| Mint | `#059669` | `#34D399` | Emerald |
| Lavender | `#7C3AED` | `#A78BFA` | Violet |
| Coral | `#E11D48` | `#FB7185` | Rose |

All four accents also update the Nuxt UI primary scale so buttons, focus rings,
selection states and navigation share the selected color.

### 2.4 Semantic colours

Each semantic role has **three tokens**:

- `soft` — pastel tinted background. Used for fills (badges, banners, alert backgrounds, validation field tint).
- `text` — semantic text and label colour. Chosen so it meets **WCAG AA (≥ 4.5:1)** against its `soft` background. AAA where it costs nothing.
- `accent` — fully saturated semantic colour. Used for icons, 2–3 px rails, 1 px borders, destructive action buttons, and the inner colour of focus rings on semantic inputs. **Never** as a large fill.

**The pastel pattern is uniform across all four semantics.** The clinical urgency of an alert is communicated by the icon, the accent rail and (for the most critical surfaces) a 1 px border in `accent` — not by saturating the fill. This keeps the UI calm during long shifts while preserving identification under a glance.

| Role | Accent (light) | Accent (dark) | Soft bg (light) | Soft bg (dark) | Text (light) | Text (dark) | Use |
|---|---|---|---|---|---|---|---|
| `success` | `#0F9D58` | `#34D399` | `#E6F6EC` | `rgba(52,211,153,0.10)` | `#15803D` | `#86EFAC` | Paid, completed, performed |
| `info` | `#0284C7` | `#7DD3FC` | `#E0F2FE` | `rgba(125,211,252,0.10)` | `#075985` | `#BAE6FD` | Informational badges |
| `warning` | `#D97706` | `#F59E0B` | `#FEF3E2` | `rgba(245,158,11,0.12)` | `#9A3412` | `#FCD34D` | Pending, expiring plan, scheduling overlap |
| `danger` | `#DC2626` | `#F87171` | `#FEE7E7` | `rgba(248,113,113,0.12)` | `#991B1B` | `#FCA5A5` | Allergies, contraindications, conflicts, deletion, billing errors, validation errors |

**Alert surface anatomy** (applies to `PatientAlertsBanner`, conflict cells, validation messages, destructive confirmations):

```
┌─[ rail 3px in --color-{role}-accent ]─────────────────────┐
│                                                            │
│  [icon in accent]  Title in --color-{role}-text (semibold) │
│                    Body in --color-{role}-text (regular)   │
│                                                            │
└─ background: --color-{role}-soft  ─────────────────────────┘
```

For the most clinically critical surface (allergies banner, scheduling conflict block) add a 1 px outer border in `--color-{role}-accent` for a slightly stronger frame. Still no saturated fill.

### 2.5 Professional colours (calendar)

Per-professional colours are assigned in `useProfessionals()`. Calendar blocks render the **fill at alpha 0.12** with a **3 px solid left border** in the professional's full colour. This communicates ownership without saturating the daily view.

---

## 3. Typography

### 3.1 Font

- **Family:** `Inter Variable`, auto-hosted via `@fontsource-variable/inter` (no CDN). Fallback chain: `-apple-system, system-ui, "Segoe UI", Helvetica, Arial`.
- **Weights loaded:** 400, 500, 600, 700 (variable axis covers all).
- **OpenType features (global):**
  - `"cv11"` — alternate `1`/`l`/`I` to disambiguate in clinical data.
  - `"ss01"` — single-storey `a` (cleaner at small sizes).
  - `"tnum"` — tabular numerals so amounts, doses, times and FDI tooth numbers align in tables.

### 3.2 Scale

| Token | Size | Line-height | Tracking | Weight | Use |
|---|---|---|---|---|---|
| `--text-display` | 28 px | 1.15 | -0.4 px | 700 | Page titles, KPI numerals |
| `--text-h1` | 22 px | 1.25 | -0.25 px | 700 | Modal titles, section heads |
| `--text-h2` | 18 px | 1.30 | -0.15 px | 600 | Sub-sections, card headers |
| `--text-h3` | 15 px | 1.35 | normal | 600 | Mini panel headers |
| `--text-body` | 14 px | 1.50 | normal | 400 | **Default body** |
| `--text-body-prose` | 15 px | 1.55 | normal | 400 | Clinical notes, anamnesis (long-form reading) |
| `--text-ui` | 14 px | 1.30 | normal | 500 | Form labels, nav items |
| `--text-button` | 14 px | 1.20 | normal | 600 | Buttons |
| `--text-caption` | 12 px | 1.40 | 0.1 px | 500 | Metadata, timestamps, badges |
| `--text-micro` | 11 px | 1.30 | 0.2 px | 600 | Dense odontogram tags |

**Why not 16 px body?** A 16 px body inflates tables, treatment lists and calendar blocks. We default to 14 px and step up to 15 px specifically for reading-prose contexts (notes, anamnesis).

### 3.3 i18n

Spanish copy runs ~20% longer than English. Apply:

- `text-wrap: pretty` on headings and short labels.
- Flexible `min-width` on nav items — never fix widths that fit only English.
- Avoid `text-overflow: ellipsis` on patient names and treatments unless the full string is exposed in a tooltip.

---

## 4. Spacing, Radius and Elevation

### 4.1 Spacing scale

Base 4 px. Use Tailwind's default scale: `0, 1 (4), 2 (8), 3 (12), 4 (16), 5 (20), 6 (24), 8 (32), 10 (40), 12 (48), 16 (64)`.

Vertical rhythm guidance:
- Between page sections: 32–48 px.
- Between cards in a grid: 16–24 px.
- Inside a card: 16 px (comfortable) / 12 px (compact).
- Between form fields: 16 px (comfortable) / 12 px (compact).

### 4.2 Radius

| Token | Value | Use |
|---|---|---|
| `--radius-xs` | 4 px | Inline inputs, small buttons |
| `--radius-sm` | 6 px | Standard buttons, chips |
| `--radius-md` | 8 px | Form inputs, list items |
| `--radius-lg` | 12 px | Standard cards |
| `--radius-xl` | 16 px | Modals, featured panels |
| `--radius-pill` | 9999 px | Badges, avatars, status pills |

### 4.3 Elevation

Light mode uses stacked low-opacity shadows. Dark mode uses **surface colour** to communicate elevation; shadows are disabled.

```css
:root {
  --shadow-xs: 0 1px 1px rgba(15,17,22,0.02);
  --shadow-sm: 0 1px 2px rgba(15,17,22,0.03), 0 1px 1px rgba(15,17,22,0.02);
  --shadow-md: 0 4px 12px rgba(15,17,22,0.04), 0 1px 3px rgba(15,17,22,0.03);
  --shadow-lg: 0 14px 28px rgba(15,17,22,0.05), 0 4px 12px rgba(15,17,22,0.03);
}

.dark {
  --shadow-xs: none;
  --shadow-sm: none;
  --shadow-md: none;
  --shadow-lg: none;
}
```

| Level | Light treatment | Dark treatment | Use |
|---|---|---|---|
| Flat | None | None | Page background, text blocks |
| Whisper | `1px solid var(--color-border)` | Same | Card outlines, dividers |
| Soft | `--shadow-sm` | Surface = `--color-surface` (one step up from canvas) | Standard cards |
| Medium | `--shadow-md` | Surface = `--color-surface-muted` | Popovers, dropdowns |
| Deep | `--shadow-lg` + border | Surface = `--color-surface` + border | Modals |

---

## 5. Density Modes

Two global modes, persisted in `localStorage` as `ui:density = comfortable | compact`, applied as a class on `<html>` and exposed by the `useDensity()` composable.

| Density | Card padding | Table row | Button padding | Body size |
|---|---|---|---|---|
| `comfortable` (default) | 16 / 20 px | 44 px | 8 / 14 px | 14 px |
| `compact` | 10 / 14 px | 32 px | 6 / 10 px | 13 px |

**Forced compact** (regardless of preference): `OdontogramChart`, `AppointmentDailyView`, `AppointmentCalendar`, `TreatmentListSection`. These views are inherently dense.

**Forced comfortable**: `MedicalHistoryForm`, `PatientQuickInfo`, dashboard (`pages/index.vue`), `EmergencyContactForm`, `LegalGuardianForm`, `AppointmentModal`.

**Mobile/tablet override**: tap targets must stay ≥ 44 px. On `< 1024 px` viewports, `comfortable` is forced regardless of user preference.

---

## 6. Components

Components in Dentum are built on **Nuxt UI 4** (Radix Vue under the hood). Customisation happens centrally via `app.config.ts`, not per-call.

### 6.1 Buttons (`UButton`)

| Variant | Background | Text | Border | Use |
|---|---|---|---|---|
| `solid` (primary) | `--color-primary` | white | none | Primary CTA — one per view |
| `soft` | `--color-primary-soft` | `--color-primary-soft-text` | none | Secondary actions |
| `outline` | transparent | `--color-text` | `--color-border` | Tertiary actions |
| `ghost` | transparent | `--color-text` | none | In-row actions, icon buttons |
| `link` | transparent | `--color-primary` | none | Inline navigation |

- Sizing: `sm` is the default (`14 px` text, 8/14 px padding). `xs` for in-row actions in tables.
- Radius: `--radius-sm`.
- Hover: background shifts one step (e.g. `--color-primary` → `--color-primary-hover`).
- Active: no scale transform (avoid micro-motion in clinical UI).
- Focus: 2 px ring in `--color-primary`, 2 px offset.
- Loading: spinner replaces leading icon, button stays the same width (no layout shift).

Permission-gated buttons follow the same defaults — gate with `v-if="can(PERMISSIONS.x.y)"` on a plain `UButton`.

### 6.2 Cards (`UCard`)

- Background: `--color-surface`.
- Border: `1px solid var(--color-border)`.
- Shadow: `--shadow-sm` (light); none (dark — relies on surface colour).
- Radius: `--radius-lg` (12 px).
- Header padding: 16 / 20 px (comfortable), 10 / 14 px (compact).
- No header divider unless visually necessary; rely on weight/size hierarchy.

### 6.3 Inputs and Forms

- Background: `--color-surface-sunken`.
- Border: `1px solid var(--color-border)`.
- Radius: `--radius-md`.
- Focus: border becomes `--color-primary`, ring 2 px in `--color-primary`.
- Placeholder: `--color-text-subtle`.
- Labels: `--text-ui`, sit above field with 6 px gap.
- Help/error text: `--text-caption`, sits below with 4 px gap.
- Required marker: small red dot `•` after label; never an asterisk in superscript (legibility).

### 6.4 Badges (`UBadge`)

- Default and **only** variant: `soft` — filled with `--color-{role}-soft` background and `--color-{role}-text` text. Same pattern across success, info, warning, danger.
- For badges that need extra emphasis (e.g., "Vencido", "Conflicto", "Validation error") add a small leading dot or icon in `--color-{role}-accent`. **Do not** swap the fill to a saturated colour.
- Radius: `--radius-pill`.
- Padding: 2 / 8 px.
- Font: `--text-caption`.

### 6.5 Modals (`UModal`)

- Surface: `--color-surface`.
- Radius: `--radius-xl`.
- Border: `1px solid var(--color-border)`.
- Shadow: `--shadow-lg` (light); none + border (dark).
- Backdrop: `rgba(15, 17, 22, 0.40)` (light), `rgba(0, 0, 0, 0.55)` (dark).
- Width: 480 px (form), 560 px (form with sections), 720 px (data-heavy).
- Close button: top-right, `ghost` variant.
- Focus trap: enforced, returns focus to trigger on close.

### 6.6 Tables

- No outer border. Outer separation comes from the surrounding card.
- Row separator: `1px solid var(--color-border-subtle)`.
- Header row: `--text-caption`, weight 600, colour `--color-text-muted`, no background, no top border.
- Hover row: `--color-surface-muted`.
- Selected row: `--color-primary-soft`.
- Numeric columns: right-aligned, `tnum` active.
- Action column: ghost icon buttons, right-aligned, only visible on row hover (desktop) or always (touch).

### 6.7 Navigation (sidebar in `layouts/default.vue`)

- Background: `--color-surface-muted`.
- No border-right (separation by colour, not by line).
- Item: 8 / 12 px padding, `--radius-md`, `--text-ui`.
- Hover item: `--color-surface`.
- Active item: `--color-primary-soft` background, `--color-primary-soft-text` text and icon. **No fully saturated `bg-primary-500`** — too loud in long sessions.
- Collapsed sidebar: 56 px width, only icons, tooltips on hover.

### 6.8 Header (top bar)

- Background: `--color-surface`.
- Bottom border: `1px solid var(--color-border-subtle)`.
- Height: 56 px.
- Houses: sidebar toggle, clinic name, density toggle, colour-mode toggle, logout.

### 6.9 Empty states

Use the shared `EmptyState` component. Pattern:

- Icon (32 px, `--color-text-subtle`).
- Title (`--text-h2`).
- Description (`--text-body`, `--color-text-muted`).
- Single primary action.

### 6.10 Page header

Use the shared `PageHeader` component with slots `title`, `subtitle`, `actions`, `tabs`. Standardises spacing and typography across all pages.

---

## 7. Module-Specific Guidance

### 7.1 Patient alerts (`PatientAlertsBanner`)

This banner communicates allergies, contraindications and ASA status. Use the **alert surface anatomy** from §2.4:

- Background: `--color-danger-soft` (allergies, contraindications) or `--color-warning-soft` (cautions, ASA III/IV pre-op notes).
- Text: `--color-{role}-text` (≥ 4.5:1 against the soft background).
- Icon and 3 px left rail: `--color-{role}-accent`.
- 1 px outer border in `--color-{role}-accent` for allergies and absolute contraindications (highest clinical urgency).
- Always icon + text + colour — never colour alone.
- Sticky to the top of the patient view; collapses to a one-line indicator on scroll, keeping the icon and rail visible.

This delivers immediate recognition without the wall-of-red effect that wears down clinicians across an 8-hour shift.

### 7.2 Odontogram

The odontogram has its own CSS variables (legacy, in `main.css`). They must be **derived from the new tokens**, not redefined:

| Odontogram var | Light source | Dark source |
|---|---|---|
| `--odontogram-bg` | `--color-surface-muted` | `--color-surface-muted` |
| `--odontogram-fill` | `--color-surface` | `--color-surface` |
| `--odontogram-fill-shade` | `--color-surface-sunken` | `--color-surface-sunken` |
| `--odontogram-outline` | `rgba(15,17,22,0.55)` | `rgba(255,250,240,0.55)` |
| `--odontogram-detail` | `rgba(15,17,22,0.20)` | `rgba(255,250,240,0.20)` |
| `--odontogram-selected` | `--color-primary` | `--color-primary` |

Treatment colour codes in `TreatmentIcons.ts` carry clinical meaning. **Do not change them.** Verify each maintains 4.5:1 contrast against the new fill in both modes; if any fails, adjust the icon colour, not the importance.

Force `compact` density. Tooltip uses `--shadow-md` and a whisper border.

### 7.3 Calendar (weekly + daily)

- Force `compact` density.
- Grid lines: `--color-border-subtle`.
- Appointment block: fill = professional colour at alpha 0.12, left border 3 px in full professional colour.
- `cancelled`: opacity 0.5 + strikethrough on the title. Not a red fill (it's a state, not an alert).
- `conflict` / overlap: alert surface — fill `--color-danger-soft` at low alpha overlay on the existing professional fill, 1 px outer border in `--color-danger-accent`, small warning icon in `--color-danger-accent` top-right. Identifiable as an alert without saturating the time slot.
- Drag preview: dashed border in `--color-primary`.

### 7.4 Treatment lists, plans, budgets

- All status badges use the soft pattern (no bold fills). For "Vencido" (overdue) and validation errors, add a leading dot/icon in `--color-danger-accent` instead of swapping the fill.
- Inline form validation errors: tinted field background `--color-danger-soft` (alpha low), border 1 px in `--color-danger-accent`, helper text below in `--color-danger-text`.
- Amounts and totals: right-aligned, `tnum`, weight 600 for the total row.
- Multi-tooth treatment groups: subtle left rail in `--color-primary-soft` to communicate grouping without a heavy border.

### 7.5 Login (`pages/login.vue`)

- Centred card, max-width 400 px.
- No decorative background. `--color-canvas` everywhere.
- Logo + product name above the card.
- Single primary button, soft "forgot password" link below.

---

## 8. Accessibility (WCAG AA, clinical floor)

Non-negotiable:

- **Contrast**: body text 4.5:1, large text 3:1, UI components 3:1, in both modes.
- **Focus visible**: 2 px ring + 2 px offset on every interactive element. Never `outline: none` without a replacement.
- **Hit targets**: ≥ 44 × 44 px on mobile/tablet (gabinete is often used on tablet).
- **Motion**: `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; } }`.
- **Semantic HTML**: `<button>` for actions, `<a>` for navigation, `<nav>`, `<main>`, `<aside>`, `<section>`. One `<h1>` per page.
- **Keyboard navigation**: every flow operable without a mouse. No focus traps outside modals.
- **Colour is never the only signal**: alerts always combine icon + text + colour.
- **Screen readers**: all icon-only buttons have `aria-label` (or visible label). Status badges use `role="status"` for announcements when state changes.

---

## 9. Motion

- Allowed transitions: `background-color`, `border-color`, `color`, `opacity`, `transform`, `box-shadow`.
- Default duration: 150 ms.
- Default easing: `cubic-bezier(0.2, 0, 0.2, 1)` (standard easing).
- **Forbidden**: scale transforms on click, parallax, decorative loops, autoplay.
- All transitions disabled under `prefers-reduced-motion: reduce`.

---

## 10. Implementation Reference

### 10.1 Files

- `frontend/app/assets/css/main.css` — token definitions (`:root` + `.dark`), font loading, base resets.
- `frontend/app/assets/css/typography.css` — typography utilities (`.text-display`, `.text-h1`, …) and `font-feature-settings`.
- `frontend/app/app.config.ts` — Nuxt UI theme: `primary: 'sky'`, `neutral: 'stone'`, component slot overrides.
- `frontend/nuxt.config.ts` — register `@fontsource-variable/inter`.
- `frontend/app/composables/useDensity.ts` — density toggle + persistence.
- `frontend/app/components/shared/DensityToggle.vue` — UI control in header.
- `frontend/app/components/shared/PageHeader.vue` — standard page header.
- `frontend/app/components/shared/EmptyState.vue` — standard empty state.

### 10.2 Nuxt UI configuration

```ts
// app.config.ts
export default defineAppConfig({
  ui: {
    colors: { primary: 'sky', neutral: 'stone' },
    button: {
      defaultVariants: { size: 'sm', color: 'neutral', variant: 'soft' }
    },
    card: {
      slots: {
        root: 'bg-[var(--color-surface)] ring-1 ring-[var(--color-border)] shadow-[var(--shadow-sm)] rounded-[var(--radius-lg)]'
      }
    },
    badge: {
      defaultVariants: { variant: 'soft', size: 'sm' }
    }
  }
})
```

### 10.3 Tailwind / Nuxt UI mapping

Prefer Tailwind utility classes that already point at our tokens via Nuxt UI's `--ui-*` variables. When a component needs a token directly, use arbitrary value syntax: `bg-[var(--color-surface-muted)]`.

---

## 11. Agent Prompt Guide

Quick reference for AI contributors:

### Colour choices
- Page background → `--color-canvas`.
- Card / modal background → `--color-surface`.
- Sidebar / alternating row → `--color-surface-muted`.
- Input background → `--color-surface-sunken`.
- Primary text → `--color-text`. Secondary → `--color-text-muted`. Hint → `--color-text-subtle`.
- Border → `--color-border`. Divider → `--color-border-subtle`.
- Primary action → `--color-primary`.
- Status badges and alerts → always semantic *soft* fill + *text* + *accent* (icon/rail). Same pattern across success, info, warning, danger.
- Destructive action button → `solid` variant in `--color-danger-accent`. This is the only place danger appears as a large fill.

### Typography choices
- Page title → `--text-display` weight 700.
- Card header → `--text-h2` weight 600.
- Table cell, list item → `--text-body` (14 px).
- Long-form notes → `--text-body-prose` (15 px).
- Badge, timestamp → `--text-caption` (12 px).
- Always activate `tnum` on numeric columns.

### Component defaults
- Buttons → `size: 'sm'`, `variant: 'soft'`, `color: 'neutral'`. Use `solid` + `primary` only for the single primary CTA per view.
- Cards → no extra border, rely on `--shadow-sm` (light) or surface step (dark).
- Modals → 480 px (form), 720 px (data).
- Empty states → use `EmptyState` component.
- Page wrappers → use `PageHeader` component.

### Forbidden patterns
- Hardcoded hex colours in components.
- `bg-white`, `bg-gray-*`, `bg-slate-*` directly. Use tokens.
- `text-3xl`, `text-2xl` for headings. Use typography utilities.
- Decorative animations or scale transforms.
- Saturated `accent` colour as a large fill (banner/cell/badge background). The only fills allowed for semantics are `--color-{role}-soft`. Saturated `accent` is for icons, rails (2–3 px), borders (1 px) and destructive buttons.
- Dropping the icon or rail from an alert "to clean it up". The icon and rail carry the semantic identity once the fill is pastel.
- Loud saturated nav backgrounds (use `--color-primary-soft`, not `bg-primary-500`).
- `outline: none` without a focus replacement.

### Iteration checklist
When adding or modifying a view:

1. Does any clinical signal lose contrast or stop being identifiable at a glance? → Revert. (Pastel fill is fine; missing icon/rail or text contrast below 4.5:1 is not.)
2. Did I add a border or shadow I could have replaced with spacing? → Remove.
3. Did I introduce a new colour outside the token set? → Use a token.
4. Does the view work at both densities? → Test both, force one if dense.
5. Does it pass WCAG AA in light **and** dark? → Run contrast check.
6. Does it respect `prefers-reduced-motion`? → Test.
7. Does Spanish copy fit? → Test with the longest realistic strings.
