"""Chip-catalog seed defaults (issue #270 §4, slice-a seed-only)."""

from __future__ import annotations

DEFAULT_WIRES: tuple[str, ...] = (
    "NiTi .012",
    "NiTi .014",
    "NiTi .016",
    "NiTi .018",
    "NiTi .016x.022",
    "NiTi .017x.025",
    "NiTi .019x.025",
    "Steel .016",
    "Steel .018",
    "Steel .017x.025",
    "Steel .019x.025",
    "TMA .017x.025",
    "Braided",
)

DEFAULT_PROCEDURES: tuple[str, ...] = (
    "power_chain",
    "elastics_class_2",
    "elastics_class_3",
    "niti_open_coil",
    "metal_ligature",
    "ligature_change",
    "button_attachment",
    "ipr",
    "bite_turbos",
    "bracket_rebonding",
    "expander_activation",
    "band_placement",
    "bracket_removal",
    "retainer_placement",
)
