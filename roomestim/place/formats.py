"""Immersive speaker-format angle catalog (P7.2) — ANGLES ONLY.

A small table of canonical listener-relative loudspeaker angles for the common
surround / immersive bed+height formats (``5.1`` … ``9.1.6``). This is the
format anchor for Mode A obstacle-aware placement
(:func:`roomestim.place.obstacle_aware.place_format_avoid`): each channel's
ideal world point is ``ear + yaml_speaker_to_cartesian(az, el, radius)``.

Provenance (PUBLIC guidance only — NO paywalled standard):
    * Bed/surround azimuths — ITU-R Recommendation BS.775 loudspeaker layout
      (L/R ±30°, C 0°, surround Ls/Rs ±110°; 7.1 side ±90° / back ±150°).
    * Height elevation — Dolby Atmos Home Theater Installation Guidelines
      (public): height speakers 30-55° elevation, 45° ideal. The catalog reuses
      the EXISTING repo constant :data:`roomestim.place.standards.HEIGHT_EL_IDEAL_DEG`
      (45°) rather than hard-coding a duplicate.
    * Height/wide azimuths — Dolby Atmos Home guidelines (front height ~±45°,
      top-middle ~±90°, rear height ~±135°; front-wide ~±60°).

These angles are RECONSTRUCTED from the PUBLIC guidance above; they are NOT the
CTA/CEDIA RP22 standard (whose full text is paywalled — mirroring the honesty
precedent in :mod:`roomestim.place.standards`). LFE is a non-directional channel
and is catalogued at a nominal front (az 0°, el 0°) position purely so the
channel count matches the format id.

Azimuth convention follows :mod:`roomestim.coords`: RIGHT = ``+az`` measured from
the front (``+z``); UP = ``+el``. Left channels therefore carry negative azimuth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from roomestim.place.standards import HEIGHT_EL_IDEAL_DEG

__all__ = [
    "FORMAT_CATALOG",
    "FORMAT_PROVENANCE_NOTE",
    "FormatChannel",
    "ImmersiveFormat",
    "get_format",
    "list_format_ids",
]

#: Single source of truth for the catalog provenance (referenced by each
#: :class:`ImmersiveFormat.note`; do not retype). Reconstructed from PUBLIC
#: guidance only — never a paywalled standard.
FORMAT_PROVENANCE_NOTE: str = (
    "Canonical angles reconstructed from PUBLIC guidance only: ITU-R BS.775 "
    "bed/surround azimuths (L/R +/-30, C 0, surround +/-110; 7.1 side +/-90, "
    "back +/-150) and Dolby Atmos Home Theater Installation Guidelines height "
    "angles (front height +/-45, top-middle +/-90, rear height +/-135; 45 deg "
    "elevation ideal, reusing standards.HEIGHT_EL_IDEAL_DEG). NOT the paywalled "
    "CTA/CEDIA RP22 standard; LFE is non-directional (nominal front 0/0)."
)


Role = Literal["bed", "surround", "height"]


@dataclass(frozen=True)
class FormatChannel:
    """One channel's canonical listener-relative angle.

    ``az_deg`` uses the :mod:`roomestim.coords` convention (RIGHT = ``+az`` from
    the front ``+z``); ``el_deg`` is UP = ``+``. ``role`` groups the channel as a
    listener-level ``bed`` / ``surround`` speaker or an overhead ``height`` one.
    """

    name: str
    az_deg: float
    el_deg: float
    role: Role


@dataclass(frozen=True)
class ImmersiveFormat:
    """A named speaker format = an ordered tuple of :class:`FormatChannel`.

    The channel count matches the format id (``5.1`` -> 6, ``7.1.4`` -> 12,
    ``9.1.6`` -> 16; the ``.1`` LFE and every ``.N`` height count as channels).
    """

    format_id: str
    channels: tuple[FormatChannel, ...]
    note: str


# --------------------------------------------------------------------------- #
# Canonical angle building blocks (public guidance; see module docstring)
# --------------------------------------------------------------------------- #

_EL_BED: float = 0.0  # bed/surround are at listener level
_EL_HEIGHT: float = HEIGHT_EL_IDEAL_DEG  # reuse existing repo constant (45 deg)

# ITU-R BS.775 bed
_L = FormatChannel("L", -30.0, _EL_BED, "bed")
_R = FormatChannel("R", 30.0, _EL_BED, "bed")
_C = FormatChannel("C", 0.0, _EL_BED, "bed")
_LFE = FormatChannel("LFE", 0.0, _EL_BED, "bed")  # non-directional; nominal front
# ITU-R BS.775 surround
_LS = FormatChannel("Ls", -110.0, _EL_BED, "surround")
_RS = FormatChannel("Rs", 110.0, _EL_BED, "surround")
# 7.1 side + back surround
_LSS = FormatChannel("Lss", -90.0, _EL_BED, "surround")
_RSS = FormatChannel("Rss", 90.0, _EL_BED, "surround")
_LSR = FormatChannel("Lsr", -150.0, _EL_BED, "surround")
_RSR = FormatChannel("Rsr", 150.0, _EL_BED, "surround")
# 9.x front-wide bed + rear surround
_LW = FormatChannel("Lw", -60.0, _EL_BED, "bed")
_RW = FormatChannel("Rw", 60.0, _EL_BED, "bed")
_LRS = FormatChannel("Lrs", -150.0, _EL_BED, "surround")
_RRS = FormatChannel("Rrs", 150.0, _EL_BED, "surround")
# Dolby Atmos Home height layer
_LTF = FormatChannel("Ltf", -45.0, _EL_HEIGHT, "height")
_RTF = FormatChannel("Rtf", 45.0, _EL_HEIGHT, "height")
_LTM = FormatChannel("Ltm", -90.0, _EL_HEIGHT, "height")
_RTM = FormatChannel("Rtm", 90.0, _EL_HEIGHT, "height")
_LTR = FormatChannel("Ltr", -135.0, _EL_HEIGHT, "height")
_RTR = FormatChannel("Rtr", 135.0, _EL_HEIGHT, "height")


def _fmt(format_id: str, channels: tuple[FormatChannel, ...]) -> ImmersiveFormat:
    return ImmersiveFormat(
        format_id=format_id, channels=channels, note=FORMAT_PROVENANCE_NOTE
    )


#: The immersive-format angle catalog (angles only). Keys are the public format
#: ids; values are :class:`ImmersiveFormat` with channel counts matching the id.
FORMAT_CATALOG: dict[str, ImmersiveFormat] = {
    "5.1": _fmt("5.1", (_L, _R, _C, _LFE, _LS, _RS)),
    "7.1": _fmt("7.1", (_L, _R, _C, _LFE, _LSS, _RSS, _LSR, _RSR)),
    "5.1.2": _fmt("5.1.2", (_L, _R, _C, _LFE, _LS, _RS, _LTF, _RTF)),
    "5.1.4": _fmt("5.1.4", (_L, _R, _C, _LFE, _LS, _RS, _LTF, _RTF, _LTR, _RTR)),
    "7.1.4": _fmt(
        "7.1.4",
        (_L, _R, _C, _LFE, _LSS, _RSS, _LSR, _RSR, _LTF, _RTF, _LTR, _RTR),
    ),
    "9.1.6": _fmt(
        "9.1.6",
        (
            _L,
            _R,
            _C,
            _LW,
            _RW,
            _LSS,
            _RSS,
            _LRS,
            _RRS,
            _LFE,
            _LTF,
            _RTF,
            _LTM,
            _RTM,
            _LTR,
            _RTR,
        ),
    ),
}


def get_format(format_id: str) -> ImmersiveFormat:
    """Return the :class:`ImmersiveFormat` for ``format_id``.

    Raises ``ValueError`` listing the known ids (fail-loud; the server maps it to
    a generic 400) when ``format_id`` is not in :data:`FORMAT_CATALOG`.
    """
    try:
        return FORMAT_CATALOG[format_id]
    except KeyError:
        raise ValueError(
            f"unknown format_id {format_id!r}; one of {list_format_ids()}"
        ) from None


def list_format_ids() -> list[str]:
    """Return the catalogued format ids in catalog (insertion) order."""
    return list(FORMAT_CATALOG.keys())
