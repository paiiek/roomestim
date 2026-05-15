"""Locked hex color palette per MaterialLabel — design §9.2."""
from __future__ import annotations

from roomestim.model import MaterialLabel

MATERIAL_PALETTE: dict[MaterialLabel, str] = {
    MaterialLabel.WALL_PAINTED:          "#E8DDD3",
    MaterialLabel.WALL_CONCRETE:         "#9C9C9C",
    MaterialLabel.WOOD_FLOOR:            "#A0522D",
    MaterialLabel.CARPET:                "#8B7355",
    MaterialLabel.GLASS:                 "#A8D8EA",
    MaterialLabel.CEILING_ACOUSTIC_TILE: "#F5F5DC",
    MaterialLabel.CEILING_DRYWALL:       "#F0F0F0",
    MaterialLabel.UNKNOWN:               "#C0C0C0",
    MaterialLabel.MISC_SOFT:             "#7B68A6",
    MaterialLabel.MELAMINE_FOAM:         "#FFB347",
}

SPEAKER_CHANNEL_PALETTE: list[str] = [
    "#E41A1C", "#377EB8", "#4DAF4A", "#984EA3",
    "#FF7F00", "#FFFF33", "#A65628", "#F781BF",
]


def speaker_color(channel: int) -> str:
    """Cycle SPEAKER_CHANNEL_PALETTE; channels >8 wrap."""
    return SPEAKER_CHANNEL_PALETTE[(channel - 1) % len(SPEAKER_CHANNEL_PALETTE)]
