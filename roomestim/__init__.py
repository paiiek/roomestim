"""roomestim — capture-to-config: room scan -> RoomModel + speaker placement -> engine YAMLs."""

__version__ = "0.19.0"
__schema_version__ = "0.2-draft"

from roomestim.edit import (  # noqa: E402
    evolve_placement,
    evolve_room,
    evolve_room_add_object,
    evolve_room_material,
    evolve_room_materials_bulk,
    evolve_room_remove_object,
    evolve_surface,
    nudge_speaker,
)
from roomestim.model import (  # noqa: E402
    DEFAULT_OBJECT_MATERIAL,
    Object,
    ObjectKind,
)

__all__ = [
    "DEFAULT_OBJECT_MATERIAL",
    "Object",
    "ObjectKind",
    "evolve_placement",
    "evolve_room",
    "evolve_room_add_object",
    "evolve_room_material",
    "evolve_room_materials_bulk",
    "evolve_room_remove_object",
    "evolve_surface",
    "nudge_speaker",
]
