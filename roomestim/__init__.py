"""roomestim — capture-to-config: room scan -> RoomModel + speaker placement -> engine YAMLs."""

__version__ = "0.16.0"
__schema_version__ = "0.1-draft"

from roomestim.edit import (  # noqa: E402
    evolve_room,
    evolve_room_material,
    evolve_room_materials_bulk,
    evolve_surface,
)

__all__ = [
    "evolve_room",
    "evolve_room_material",
    "evolve_room_materials_bulk",
    "evolve_surface",
]
