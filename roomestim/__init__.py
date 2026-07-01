"""roomestim — capture-to-config: room scan -> RoomModel + speaker placement -> engine YAMLs."""

__version__ = "0.62.0"
__schema_version__ = "0.2-draft"

from roomestim.adapters.roomplan_structure import parse_structure  # noqa: E402
from roomestim.collection import RoomCollection  # noqa: E402
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
    FREESTANDING_OBJECT_KINDS,
    WALL_ATTACHED_OBJECT_KINDS,
    Object,
    ObjectKind,
)

__all__ = [
    "DEFAULT_OBJECT_MATERIAL",
    "FREESTANDING_OBJECT_KINDS",
    "WALL_ATTACHED_OBJECT_KINDS",
    "Object",
    "ObjectKind",
    "RoomCollection",
    "evolve_placement",
    "evolve_room",
    "evolve_room_add_object",
    "evolve_room_material",
    "evolve_room_materials_bulk",
    "evolve_room_remove_object",
    "evolve_surface",
    "nudge_speaker",
    "parse_structure",
]
