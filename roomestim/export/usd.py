"""USDZ export for RoomModel + PlacementResult (v0.17 — ADR 0035 §A).

§Purpose
    Round-trip a :class:`~roomestim.model.RoomModel` (with optional
    :class:`~roomestim.model.PlacementResult`) to a USDZ package that can
    be opened in Apple Reality Composer / Xcode / iOS Quick Look. The
    on-disk hierarchy mirrors the in-memory model:

    .. code-block:: text

        /Room/Surfaces/<surface_idx>
        /Room/Objects/<object_idx>
        /Room/Listener            (when placement is provided)
        /Room/Speakers/Channel_N  (when placement is provided)

§Backend
    Uses Pixar's open-source ``usd-core`` Python distribution (D45). It is
    declared in the ``usd`` / ``mesh-export`` optional extras and lazy-
    imported inside :func:`write_usdz` so that callers without the extra
    installed can still import :mod:`roomestim.export` without crashing.

§Layering
    Pure write path — no acoustic computation here. Column geometry is
    derived from :func:`roomestim.reconstruct.predictor._objects_to_surfaces`
    so the visual scene matches the predictor's view of object surfaces.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from roomestim.model import (
    FREESTANDING_OBJECT_KINDS,
    MaterialAbsorption,
    MaterialAbsorptionBands,
    MaterialLabel,
    PlacementResult,
    Point3,
    RoomModel,
)
from roomestim.reconstruct._disclosure import RT60_DISCLOSURE, RT60_MODEL_NAME

if TYPE_CHECKING:
    pass  # pxr is intentionally not imported at module load.

__all__ = ["write_usdz"]


# --------------------------------------------------------------------------- #
# Color palette for PBR baseColor (mirror roomestim_web.material_palette).
# Web is a different lane (D29); duplicating the palette here avoids a
# cross-lane import.
# --------------------------------------------------------------------------- #


_MATERIAL_BASECOLOR_RGB: dict[str, tuple[float, float, float]] = {
    "wall_painted":           (0.910, 0.866, 0.827),
    "wall_concrete":          (0.612, 0.612, 0.612),
    "wood_floor":             (0.627, 0.322, 0.176),
    "carpet":                 (0.545, 0.451, 0.333),
    "glass":                  (0.659, 0.847, 0.918),
    "ceiling_acoustic_tile":  (0.961, 0.961, 0.863),
    "ceiling_drywall":        (0.941, 0.941, 0.941),
    "unknown":                (0.753, 0.753, 0.753),
    "misc_soft":              (0.482, 0.408, 0.651),
    "melamine_foam":          (1.000, 0.702, 0.278),
}


def _hex_to_rgb(material: str) -> tuple[float, float, float]:
    return _MATERIAL_BASECOLOR_RGB.get(material, (0.6, 0.6, 0.6))


# --------------------------------------------------------------------------- #
# Lazy pxr import
# --------------------------------------------------------------------------- #


def _import_pxr() -> Any:
    """Import ``pxr`` lazily with a helpful ImportError when missing."""
    try:
        # Import the submodules explicitly: ``import pxr`` alone does not
        # populate ``pxr.Usd`` / ``pxr.UsdGeom`` / ``pxr.UsdUtils`` etc. — each
        # is a separate C-extension module. Without this the attribute reads
        # below (``pxr.UsdUtils``) raise AttributeError once pxr is installed.
        import pxr
        from pxr import (  # noqa: F401
            Gf,
            Sdf,
            Usd,
            UsdGeom,
            UsdUtils,
            Vt,
        )
    except ImportError as exc:
        raise ImportError(
            "USDZ export requires the [usd] extra; install with "
            "`pip install 'roomestim[usd]'` or `pip install 'roomestim[mesh-export]'`."
        ) from exc
    return pxr


# --------------------------------------------------------------------------- #
# Surface / object → mesh primitive helpers
# --------------------------------------------------------------------------- #


def _polygon_face_indices(vertex_count: int) -> tuple[list[int], list[int]]:
    """Return ``(face_vertex_counts, face_vertex_indices)`` for a single ngon.

    USD permits a single n-gon face per polygon, so we emit one face whose
    indices are ``[0, 1, …, n-1]``. (Consuming renderers handle the
    fan-triangulation internally.)
    """
    return ([vertex_count], list(range(vertex_count)))


def _add_mesh_prim(
    stage: Any,
    pxr: Any,
    prim_path: str,
    polygon: list[Point3],
    material_label: str,
) -> Any:
    """Create one :class:`UsdGeom.Mesh` prim from a single polygon."""
    UsdGeom = pxr.UsdGeom
    Sdf = pxr.Sdf
    Vt = pxr.Vt

    mesh = UsdGeom.Mesh.Define(stage, prim_path)
    points = [(p.x, p.y, p.z) for p in polygon]
    counts, indices = _polygon_face_indices(len(polygon))
    mesh.CreatePointsAttr(Vt.Vec3fArray(points))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(counts))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(indices))

    # Per-prim displayColor so the mesh renders without a separately bound
    # material when opened in Quick Look.
    rgb = _hex_to_rgb(material_label)
    mesh.CreateDisplayColorAttr(Vt.Vec3fArray([rgb]))

    # Store a kind metadata + custom material attribute for downstream tools.
    mesh.GetPrim().CreateAttribute(
        "roomestim:material", Sdf.ValueTypeNames.Token
    ).Set(material_label)
    return mesh


def _add_xform_marker(stage: Any, pxr: Any, prim_path: str, position: Point3) -> Any:
    """Create a simple Xform with a translate op (listener / speaker marker)."""
    UsdGeom = pxr.UsdGeom
    Gf = pxr.Gf
    xform = UsdGeom.Xform.Define(stage, prim_path)
    xform.AddTranslateOp().Set(Gf.Vec3f(position.x, position.y, position.z))
    return xform


# --------------------------------------------------------------------------- #
# Stage builder
# --------------------------------------------------------------------------- #


def _room_to_usd_stage(
    room: RoomModel,
    placement: PlacementResult | None,
) -> Any:
    """Build an in-memory :class:`pxr.Usd.Stage` from ``room`` + ``placement``.

    Returns the freshly-created stage; the caller is responsible for export.
    """
    pxr = _import_pxr()
    Usd = pxr.Usd
    UsdGeom = pxr.UsdGeom

    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    # /Room (default prim)
    room_prim = UsdGeom.Xform.Define(stage, "/Room")
    stage.SetDefaultPrim(room_prim.GetPrim())

    # /Room/Surfaces/<idx>
    UsdGeom.Xform.Define(stage, "/Room/Surfaces")
    for i, surf in enumerate(room.surfaces):
        _add_mesh_prim(
            stage,
            pxr,
            f"/Room/Surfaces/Surface_{i}",
            surf.polygon,
            surf.material.value,
        )

    # /Room/Objects/<idx>
    if room.objects:
        UsdGeom.Xform.Define(stage, "/Room/Objects")
        # Reuse the predictor's column→5-face decomposition for column
        # objects so the visual scene matches the acoustic surface model.
        try:
            from roomestim.reconstruct.predictor import _objects_to_surfaces

            column_surfaces = _objects_to_surfaces(list(room.objects))
        except Exception:
            column_surfaces = []
        column_cursor = 0
        for obj_idx, obj in enumerate(room.objects):
            obj_root = f"/Room/Objects/Object_{obj_idx}"
            UsdGeom.Xform.Define(stage, obj_root)
            if obj.kind in FREESTANDING_OBJECT_KINDS:
                # Emit the 5 column faces using the predictor's decomposition.
                for face_i in range(5):
                    if column_cursor >= len(column_surfaces):
                        break
                    cs = column_surfaces[column_cursor]
                    column_cursor += 1
                    _add_mesh_prim(
                        stage,
                        pxr,
                        f"{obj_root}/Face_{face_i}",
                        cs.polygon,
                        cs.material.value,
                    )
            else:
                # Door / window: emit a single quad in the wall plane. Without
                # access to wall-local axes we render an axis-aligned quad
                # centred on ``anchor`` in the X / Y plane as a visual stand-in.
                a = obj.anchor
                hw = obj.width_m / 2.0
                hh = obj.height_m / 2.0
                quad = [
                    Point3(a.x - hw, a.y, a.z),
                    Point3(a.x + hw, a.y, a.z),
                    Point3(a.x + hw, a.y + hh * 2.0, a.z),
                    Point3(a.x - hw, a.y + hh * 2.0, a.z),
                ]
                _add_mesh_prim(
                    stage,
                    pxr,
                    f"{obj_root}/Quad",
                    quad,
                    obj.material.value,
                )

    # /Room/Listener + /Room/Speakers/Channel_N — only when placement provided.
    if placement is not None:
        centroid_2d = room.listener_area.centroid
        listener_pt = Point3(
            centroid_2d.x, room.listener_area.height_m, centroid_2d.z
        )
        _add_xform_marker(stage, pxr, "/Room/Listener", listener_pt)
        UsdGeom.Xform.Define(stage, "/Room/Speakers")
        for sp in placement.speakers:
            _add_xform_marker(
                stage,
                pxr,
                f"/Room/Speakers/Channel_{int(sp.channel)}",
                sp.position,
            )

    return stage


# --------------------------------------------------------------------------- #
# Acoustic sidecar
# --------------------------------------------------------------------------- #


def _build_acoustics_sidecar(room: RoomModel) -> dict[str, Any]:
    """Return per-surface acoustic metadata for the ``.acoustics.json`` sidecar."""
    surfaces_out: list[dict[str, Any]] = []
    for i, surf in enumerate(room.surfaces):
        bands = surf.absorption_bands or MaterialAbsorptionBands[surf.material]
        surfaces_out.append(
            {
                "surface_idx": i,
                "kind": surf.kind,
                "material": surf.material.value,
                "absorption_500hz": float(surf.absorption_500hz),
                "absorption_bands_125_250_500_1000_2000_4000": [
                    float(b) for b in bands
                ],
            }
        )
    objects_out: list[dict[str, Any]] = []
    for i, obj in enumerate(room.objects):
        bands = MaterialAbsorptionBands[obj.material]
        objects_out.append(
            {
                "object_idx": i,
                "kind": obj.kind,
                "material": obj.material.value,
                "absorption_500hz": float(MaterialAbsorption[obj.material]),
                "absorption_bands_125_250_500_1000_2000_4000": [
                    float(b) for b in bands
                ],
                "width_m": float(obj.width_m),
                "height_m": float(obj.height_m),
                "depth_m": float(obj.depth_m),
                "wall_index": obj.wall_index,
            }
        )
    materials_unknown = any(
        s.material == MaterialLabel.UNKNOWN for s in room.surfaces
    ) or any(o.material == MaterialLabel.UNKNOWN for o in room.objects)
    return {
        "version": "0.17",
        "room_name": room.name,
        "schema_version": room.schema_version,
        # Honest acoustics labeling (additive; numbers above unchanged). Any RT60
        # derived from these absorption values is a MODEL estimate, not measured.
        "acoustics_model": RT60_MODEL_NAME,
        "disclaimer": RT60_DISCLOSURE,
        "materials_status": "UNKNOWN/assumed" if materials_unknown else "assigned",
        "surfaces": surfaces_out,
        "objects": objects_out,
    }


def _write_acoustics_sidecar(room: RoomModel, out_path: Path) -> None:
    sidecar = out_path.with_suffix(out_path.suffix + ".acoustics.json")
    with sidecar.open("w", encoding="utf-8") as fh:
        json.dump(_build_acoustics_sidecar(room), fh, indent=2)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def write_usdz(
    room: RoomModel,
    placement: PlacementResult | None,
    out_path: Path | str,
    *,
    with_acoustics_sidecar: bool = False,
) -> None:
    """Write ``room`` + optional ``placement`` to ``out_path`` as a USDZ package.

    Parameters
    ----------
    room:
        Source room model.
    placement:
        Optional placement result; listener / speaker xforms are skipped when
        ``None``.
    out_path:
        Destination ``.usdz`` file path.
    with_acoustics_sidecar:
        When True, also write ``<out_path>.acoustics.json`` carrying per-
        surface + per-object material absorption (500 Hz + 6-band).

    Raises
    ------
    ImportError
        When the ``usd-core`` extra is not installed.
    """
    pxr = _import_pxr()
    UsdUtils = pxr.UsdUtils

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stage = _room_to_usd_stage(room, placement)
    # Persist to a temporary .usdc layer, then package into a .usdz.
    tmp_usdc = out_path.with_suffix(".usdc")
    stage.GetRootLayer().Export(str(tmp_usdc))
    try:
        UsdUtils.CreateNewUsdzPackage(str(tmp_usdc), str(out_path))
    finally:
        if tmp_usdc.exists():
            tmp_usdc.unlink()

    if with_acoustics_sidecar:
        _write_acoustics_sidecar(room, out_path)
