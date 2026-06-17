"""Combined USD export for a :class:`RoomCollection` (ADR 0049, Phase 2).

USD parity of the combined glTF writer (:mod:`roomestim.export.collection_gltf`).
Builds ONE :class:`pxr.Usd.Stage` by reusing the single-room stage builder
:func:`roomestim.export.usd._room_to_usd_stage` per room and copying each room's
``/Room`` subtree under a per-room, user-offset-translated Xform
(``/Collection/Room_0``, ``/Collection/Room_1``, ...).

Honest scope (ADR 0049):
  * This is a **visual assembly** of N independent rooms at user-asserted
    offsets (:attr:`RoomCollection.offsets`). roomestim NEVER infers inter-room
    registration. When a room has no offset (``None``) its Xform carries no
    translate op — with no offsets at all the rooms overlap at the origin
    (documented, honest; not a bug).
  * There is NO geometry merge / footprint union / aggregate acoustics. Each
    room's geometry is kept intact as its own prefixed sub-tree.

The single-room writer :func:`roomestim.export.usd.write_usdz` and stage builder
:func:`roomestim.export.usd._room_to_usd_stage` are NOT touched; this module
only CALLS ``_room_to_usd_stage`` (and reuses ``_import_pxr``) and re-composes
the resulting per-room stages via :func:`pxr.Sdf.CopySpec`. The offset axis
mapping matches ``_room_to_usd_stage``'s frame exactly (Y-up, metresPerUnit
1.0): the translate is applied component-wise ``(x, y, z)`` with NO axis swap,
identical to the combined-glTF translation convention.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from roomestim.collection import RoomCollection
from roomestim.export.usd import _import_pxr, _room_to_usd_stage

__all__ = ["build_combined_stage", "write_collection_usd"]


def build_combined_stage(collection: RoomCollection) -> Any:
    """Assemble one :class:`pxr.Usd.Stage` from ``collection`` honoring offsets.

    Each room's stage (built via the single-room ``_room_to_usd_stage``) has its
    ``/Room`` subtree copied — geometry intact — under
    ``/Collection/Room_{idx}/Room``. The per-room ``/Collection/Room_{idx}``
    Xform carries a translate op equal to that room's user-supplied offset; an
    absent offset (``None``) is the identity (no translate op — the room stays
    at its local origin).

    Returns the freshly-created in-memory stage; the caller exports it.
    """
    pxr = _import_pxr()
    Usd = pxr.Usd
    UsdGeom = pxr.UsdGeom
    Gf = pxr.Gf
    Sdf = pxr.Sdf

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    collection_prim = UsdGeom.Xform.Define(stage, "/Collection")
    stage.SetDefaultPrim(collection_prim.GetPrim())
    dst_layer = stage.GetRootLayer()

    for idx, (room, placement, offset) in enumerate(
        zip(collection.rooms, collection.placements, collection.offsets)
    ):
        room_root = f"/Collection/Room_{idx}"
        room_xform = UsdGeom.Xform.Define(stage, room_root)
        if offset is not None:
            room_xform.AddTranslateOp().Set(
                Gf.Vec3f(float(offset[0]), float(offset[1]), float(offset[2]))
            )
        sub_stage = _room_to_usd_stage(room, placement)
        # Copy the per-room /Room subtree (geometry intact) under the translated
        # per-room Xform. CopySpec is a pure layer-level subtree copy across the
        # two in-memory stages — no external references, so the combined output
        # is self-contained and round-trips.
        Sdf.CopySpec(
            sub_stage.GetRootLayer(), "/Room", dst_layer, f"{room_root}/Room"
        )

    return stage


def write_collection_usd(
    collection: RoomCollection,
    out_path: Path | str,
) -> None:
    """Write ``collection`` to ``out_path`` as ONE combined USD file.

    Parameters
    ----------
    collection:
        The :class:`RoomCollection` to assemble. Each room's user-supplied
        offset (``collection.offsets[i]``) is applied as a translate op on the
        per-room Xform; absent offsets keep the room at its local origin (rooms
        may overlap — honest, documented; roomestim never infers registration).
    out_path:
        Destination file path. A ``.usdz`` suffix packages the stage into a
        USDZ archive (matching :func:`roomestim.export.usd.write_usdz`); any
        other USD suffix (``.usd`` / ``.usda`` / ``.usdc``) exports the root
        layer directly (self-contained — no external references).

    Raises
    ------
    ImportError
        When the ``usd-core`` extra is not installed.
    """
    pxr = _import_pxr()
    UsdUtils = pxr.UsdUtils

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stage = build_combined_stage(collection)

    if out_path.suffix.lower() == ".usdz":
        # Persist to a temporary .usdc layer, then package into a .usdz (mirror
        # write_usdz). The stage is self-contained (CopySpec inlines geometry),
        # so the package has no external dependencies.
        tmp_usdc = out_path.with_suffix(".usdc")
        stage.GetRootLayer().Export(str(tmp_usdc))
        try:
            UsdUtils.CreateNewUsdzPackage(str(tmp_usdc), str(out_path))
        finally:
            if tmp_usdc.exists():
                tmp_usdc.unlink()
        return

    stage.GetRootLayer().Export(str(out_path))
