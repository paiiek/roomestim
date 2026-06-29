"""Speaker specifications + a direct-field SPL engine (immersive-layout-design P1).

Additive, opt-in, numpy-free, import-safe at ``import roomestim`` time. The SPL
engine is DIRECT-FIELD ONLY — see
:data:`roomestim.reconstruct._disclosure.SPL_DIRECT_FIELD_NOTE`.
"""

from __future__ import annotations

from roomestim.spec.speaker_spec import (
    BUILTIN_SPEAKER_CATALOG,
    DEFAULT_GRID_RESOLUTION_M,
    DIRECTIVITY_ATTEN_FLOOR_DB,
    SPL_DIRECT_FIELD_NOTE,
    SpeakerProvenance,
    SpeakerSpec,
    SPLFieldScore,
    direct_field_spl_db,
    directivity_atten_db,
    format_spl_field_lines,
    load_speaker_catalog,
    load_speaker_spec,
    spl_field_over_area,
    spl_field_to_dict,
)

__all__ = [
    "BUILTIN_SPEAKER_CATALOG",
    "DEFAULT_GRID_RESOLUTION_M",
    "DIRECTIVITY_ATTEN_FLOOR_DB",
    "SPL_DIRECT_FIELD_NOTE",
    "SpeakerProvenance",
    "SpeakerSpec",
    "SPLFieldScore",
    "direct_field_spl_db",
    "directivity_atten_db",
    "format_spl_field_lines",
    "load_speaker_catalog",
    "load_speaker_spec",
    "spl_field_over_area",
    "spl_field_to_dict",
]
