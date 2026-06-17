"""CLI entry point for roomestim.

Subcommands
-----------
ingest  -- parse a capture artifact into a RoomModel; write room.yaml
place   -- load room.yaml, run placement, write layout.yaml
export  -- re-emit room.yaml + layout.yaml (idempotent)
run     -- composite: ingest + place + export
edit    -- nudge one speaker in a layout.yaml; re-validate; write + diff
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from roomestim import __version__

if TYPE_CHECKING:
    from roomestim.adapters.base import CaptureAdapter, ScaleAnchor
    from roomestim.model import PlacementResult, RoomModel


# --------------------------------------------------------------------------- #
# Argument parser helpers
# --------------------------------------------------------------------------- #


def _add_image_backend_args(p: argparse.ArgumentParser) -> None:
    """Shared `--backend image` (experimental) arguments.

    These are only meaningful for ``--backend image`` (ADR 0045 §image backend).
    The hard ``--experimental`` gate is enforced in the command handler, not at
    argparse level, so no torch import happens on the gated-out path.
    """
    p.add_argument(
        "--cam-height",
        type=float,
        default=None,
        metavar="M",
        help="Camera/tripod height in metres above the floor — the metric scale "
        "anchor for --backend image. If omitted, a default is assumed and a "
        "warning is emitted.",
    )
    p.add_argument(
        "--weights",
        choices=["st3d", "zind"],
        default="st3d",
        help="HorizonNet checkpoint for --backend image. st3d (default, "
        "Structured3D) ships; zind (Zillow, residential) is opt-in "
        "non-commercial — requires --accept-zind-tou.",
    )
    p.add_argument(
        "--accept-zind-tou",
        action="store_true",
        default=False,
        help="Accept the ZInD non-commercial Terms of Use to use --weights zind.",
    )
    p.add_argument(
        "--experimental",
        action="store_true",
        default=False,
        help="Required to use --backend image (experimental rough-estimate tier; "
        "NOT install-grade).",
    )


def _add_floor_reconstruction_arg(p: argparse.ArgumentParser) -> None:
    """Shared ``--floor-reconstruction`` arg (mesh backends only; PR3 / ADR 0042).

    Inert for non-mesh backends (``roomplan``/``image``); a stderr NOTE fires in
    ``_get_adapter`` when ``concave`` is passed to one of those, so there is no
    silent no-op.
    """
    p.add_argument(
        "--floor-reconstruction",
        choices=["convex", "concave", "occupancy", "auto"],
        default=None,
        help="Mesh footprint extraction: 'convex' (safe over-estimate), "
        "'concave' (recovers re-entrant corners; UNVALIDATED accuracy — no "
        "footprint ground truth, ADR 0042), 'occupancy' (density + "
        "connected-component footprint; rejects sparse floaters in noisy RGB-D "
        "reconstructions — robustness lever, n=1 Redwood evidence, NOT an "
        "accuracy guarantee), or 'auto' (convex-preserving: switches to "
        "occupancy ONLY when a coarse-grid signal detects a DISCONNECTED "
        "floater, else byte-equal to convex; opt-in, synthetic-fixture-"
        "validated, NOT a bleed/notch fix, ADR 0048). Default: convex; honors "
        "ROOMESTIM_MESH_FLOOR_RECON env var when unset.",
    )


def _add_ingest_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("ingest", help="Parse a capture artifact into a RoomModel.")
    p.add_argument(
        "--backend",
        choices=["roomplan", "polycam", "image"],
        required=True,
        help="Capture backend. 'image' is an EXPERIMENTAL single-panorama "
        "rough-estimate tier (requires --experimental; NOT install-grade).",
    )
    p.add_argument("--input", required=True, metavar="PATH", help="Input file path.")
    p.add_argument(
        "--out-dir",
        default=".",
        metavar="DIR",
        help="Output directory (default: cwd).",
    )
    p.add_argument(
        "--octave-band",
        action="store_true",
        default=False,
        help="Populate per-octave-band absorption block in room.yaml (opt-in; default off).",
    )
    _add_floor_reconstruction_arg(p)
    _add_image_backend_args(p)


def _add_place_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("place", help="Run speaker placement; write layout.yaml.")
    p.add_argument("--in-room", required=True, metavar="PATH", help="room.yaml path.")
    p.add_argument(
        "--algorithm",
        choices=["vbap", "dbap", "wfs", "ambisonics"],
        required=False,
        default="vbap",
        help="Placement algorithm (default: vbap).",
    )
    p.add_argument(
        "--n-speakers", type=int, default=8, metavar="N", help="Number of speakers."
    )
    p.add_argument(
        "--order",
        type=int,
        choices=[1, 2, 3],
        default=None,
        metavar="N",
        help="Ambisonics decode order (1|2|3); required for --algorithm "
        "ambisonics. order->rig: 1=octahedron(6), 2=icosahedron(12), "
        "3=dodecahedron(20). EXPERIMENTAL (rig coordinates only; SH decode/route "
        "is engine-gated and UNCONFIRMED).",
    )
    p.add_argument(
        "--layout-radius",
        type=float,
        default=2.0,
        metavar="R",
        help="VBAP ring/dome radius in metres (default 2.0).",
    )
    p.add_argument(
        "--el-deg",
        type=float,
        default=0.0,
        metavar="E",
        help="VBAP elevation in degrees (default 0.0).",
    )
    p.add_argument(
        "--wfs-f-max-hz",
        type=float,
        default=8000.0,
        metavar="F",
        help="Highest reproduction frequency for WFS spatial-aliasing bound (default 8000.0).",
    )
    p.add_argument(
        "--wfs-spacing-m",
        type=float,
        default=None,
        metavar="S",
        help="Override per-speaker spacing in metres "
        "(default: derived from --layout-radius and --n-speakers).",
    )
    p.add_argument(
        "--out-dir",
        default=".",
        metavar="DIR",
        help="Output directory (default: cwd).",
    )
    p.add_argument(
        "--check-angles",
        action="store_true",
        help=(
            "Run the geometric layout-angle check (Atmos-style): print per-speaker "
            "azimuth/elevation vs public Dolby height-speaker guidance and write a "
            "layout.angles.json sidecar. Geometry only, NO acoustic claim. Does not "
            "alter layout.yaml."
        ),
    )


def _add_export_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("export", help="Re-emit room.yaml and layout.yaml (idempotent).")
    p.add_argument("--in-room", required=True, metavar="PATH", help="room.yaml path.")
    p.add_argument(
        "--in-placement", required=True, metavar="PATH", help="layout.yaml path."
    )
    p.add_argument(
        "--out-dir",
        default=".",
        metavar="DIR",
        help="Output directory (default: cwd).",
    )
    # v0.17 (ADR 0035): export-format dispatch. "yaml" preserves the v0.16.1
    # byte-equal room.yaml + layout.yaml path; "usdz" / "gltf" / "glb" route
    # to the corresponding write_* function.
    p.add_argument(
        "--format",
        choices=["yaml", "usdz", "gltf", "glb"],
        default="yaml",
        help="Export format (default: yaml — backward-compat).",
    )
    p.add_argument(
        "--with-acoustics-sidecar",
        action="store_true",
        default=False,
        help=(
            "Write a <out>.acoustics.json sidecar carrying per-surface + per-"
            "object material absorption. Meaningful for --format usdz/gltf/glb; "
            "silently ignored for --format yaml."
        ),
    )
    # Engine validation toggle (D42 / ADR 0033): CLI flag > ENV var > default ON.
    engine_grp = p.add_mutually_exclusive_group()
    engine_grp.add_argument(
        "--validate-engine",
        metavar="PATH",
        default=None,
        help=(
            "Path to the spatial_engine repository directory. "
            "Uses SPATIAL_ENGINE_REPO_DIR env var or the documented default engine "
            "repo dir when omitted; errors with guidance if none resolve. "
            "Mutually exclusive with --no-engine-validation."
        ),
    )
    engine_grp.add_argument(
        "--no-engine-validation",
        action="store_true",
        default=False,
        help=(
            "Skip engine schema validation. A WARNING comment is prepended to the "
            "output YAML for audit-trail purposes (ADR 0033 §C). "
            "Mutually exclusive with --validate-engine."
        ),
    )


def _add_run_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("run", help="Composite: ingest + place + export.")
    p.add_argument(
        "--backend",
        choices=["roomplan", "polycam", "image"],
        required=True,
        help="Capture backend. 'image' is an EXPERIMENTAL single-panorama "
        "rough-estimate tier (requires --experimental; NOT install-grade).",
    )
    p.add_argument("--input", required=True, metavar="PATH", help="Input file path.")
    p.add_argument(
        "--algorithm",
        choices=["vbap", "dbap", "wfs", "ambisonics"],
        required=False,
        default="vbap",
        help="Placement algorithm (default: vbap).",
    )
    p.add_argument(
        "--n-speakers", type=int, default=8, metavar="N", help="Number of speakers."
    )
    p.add_argument(
        "--order",
        type=int,
        choices=[1, 2, 3],
        default=None,
        metavar="N",
        help="Ambisonics decode order (1|2|3); required for --algorithm "
        "ambisonics. order->rig: 1=octahedron(6), 2=icosahedron(12), "
        "3=dodecahedron(20). EXPERIMENTAL (rig coordinates only; SH decode/route "
        "is engine-gated and UNCONFIRMED).",
    )
    p.add_argument(
        "--layout-radius",
        type=float,
        default=2.0,
        metavar="R",
        help="VBAP ring/dome radius in metres (default 2.0).",
    )
    p.add_argument(
        "--el-deg",
        type=float,
        default=0.0,
        metavar="E",
        help="VBAP elevation in degrees (default 0.0).",
    )
    p.add_argument(
        "--wfs-f-max-hz",
        type=float,
        default=8000.0,
        metavar="F",
        help="Highest reproduction frequency for WFS spatial-aliasing bound (default 8000.0).",
    )
    p.add_argument(
        "--wfs-spacing-m",
        type=float,
        default=None,
        metavar="S",
        help="Override per-speaker spacing in metres "
        "(default: derived from --layout-radius and --n-speakers).",
    )
    p.add_argument(
        "--out-dir",
        default=".",
        metavar="DIR",
        help="Output directory (default: cwd).",
    )
    p.add_argument(
        "--octave-band",
        action="store_true",
        default=False,
        help="Populate per-octave-band absorption block in room.yaml (opt-in; default off).",
    )
    _add_floor_reconstruction_arg(p)
    _add_image_backend_args(p)
    # FIX-4 / D77: engine validation toggle (D42 / ADR 0033), at parity with
    # `export`/`edit`. CLI flag > ENV var > default ON.
    engine_grp = p.add_mutually_exclusive_group()
    engine_grp.add_argument(
        "--validate-engine",
        metavar="PATH",
        default=None,
        help=(
            "Path to the spatial_engine repository directory. "
            "Uses SPATIAL_ENGINE_REPO_DIR env var or the documented default engine "
            "repo dir when omitted; errors with guidance if none resolve. "
            "Mutually exclusive with --no-engine-validation."
        ),
    )
    engine_grp.add_argument(
        "--no-engine-validation",
        action="store_true",
        default=False,
        help=(
            "Skip engine schema validation. A WARNING comment is prepended to the "
            "output YAML for audit-trail purposes (ADR 0033 §C). "
            "Mutually exclusive with --validate-engine."
        ),
    )


def _add_edit_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser(
        "edit",
        help="Nudge one speaker in a layout.yaml; re-validate; write + unified diff.",
    )
    p.add_argument(
        "--in-placement", required=True, metavar="PATH", help="layout.yaml path."
    )
    p.add_argument(
        "--speaker",
        required=True,
        type=int,
        metavar="N",
        help="Zero-based speaker index to nudge (matches the nudge_speaker API).",
    )
    # Spherical Δ (mutually-additive deltas, not absolute values).
    p.add_argument("--daz", type=float, default=0.0, metavar="D", help="azimuth delta (degrees).")
    # NOTE: must be --del-deg, never --del; `args.del` is a Python syntax error.
    p.add_argument(
        "--del-deg", type=float, default=0.0, metavar="D",
        help="elevation delta (degrees). Resulting elevation must stay within "
             "[-90, 90]; out-of-range raises an error (exit 1).",
    )
    p.add_argument("--ddist", type=float, default=0.0, metavar="D", help="distance delta (m).")
    # Cartesian Δ (metres).
    p.add_argument("--dx", type=float, default=0.0, metavar="D", help="x delta (m).")
    p.add_argument("--dy", type=float, default=0.0, metavar="D", help="y delta (m).")
    p.add_argument("--dz", type=float, default=0.0, metavar="D", help="z delta (m).")
    p.add_argument(
        "--out-dir",
        default=".",
        metavar="DIR",
        help="Output directory for the edited layout.yaml (default: cwd).",
    )
    # Engine validation toggle (D42 / ADR 0033): CLI flag > ENV var > default ON.
    engine_grp = p.add_mutually_exclusive_group()
    engine_grp.add_argument(
        "--validate-engine",
        metavar="PATH",
        default=None,
        help=(
            "Path to the spatial_engine repository directory. "
            "Uses SPATIAL_ENGINE_REPO_DIR env var or the documented default engine "
            "repo dir when omitted; errors with guidance if none resolve. "
            "Mutually exclusive with --no-engine-validation."
        ),
    )
    engine_grp.add_argument(
        "--no-engine-validation",
        action="store_true",
        default=False,
        help=(
            "Skip engine schema validation. A WARNING comment is prepended to the "
            "output YAML for audit-trail purposes (ADR 0033 §C). "
            "Mutually exclusive with --validate-engine."
        ),
    )


def _add_collection_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Additive `collection` subcommand (ADR 0049, Phase 1).

    Composes N >= 2 explicit single-room ``room.yaml`` inputs into an ordered
    bundle: per room it runs the SAME library functions ``place`` uses and writes
    one ``room.<name>.yaml`` + ``layout.<name>.yaml``, plus a ``collection.yaml``
    manifest. roomestim does NOT infer multi-room from one capture — the bundle
    is N explicit inputs, with NO inter-room pose and NO aggregate acoustics.
    """
    p = sub.add_parser(
        "collection",
        help="Compose N single-room room.yaml inputs into a collection.yaml bundle.",
    )
    p.add_argument(
        "--in-rooms",
        required=True,
        nargs="+",
        metavar="PATH",
        help="Two or more room.yaml paths (each a genuine single-room capture).",
    )
    p.add_argument(
        "--name",
        default="collection",
        metavar="NAME",
        help="Collection/venue name (no geometric meaning; default: 'collection').",
    )
    p.add_argument(
        "--offsets",
        nargs="*",
        default=None,
        metavar="X,Y,Z",
        help="Optional USER-SUPPLIED per-room translations in metres, parallel "
        "to --in-rooms (one 'X,Y,Z' per room). roomestim NEVER infers inter-room "
        "pose; absent ⇒ identity (rooms at their own local origin).",
    )
    p.add_argument(
        "--combined-gltf",
        default=None,
        metavar="PATH",
        help="Optional path to write ONE combined glTF/GLB visual assembly of "
        "the rooms at their offsets (e.g. collection.glb). A visual assembly "
        "only — no aggregate acoustics. Recorded as 'combined_ref' in the "
        "manifest (relative to the manifest directory).",
    )
    p.add_argument(
        "--combined-usd",
        default=None,
        metavar="PATH",
        help="Optional path to write ONE combined USD visual assembly of the "
        "rooms at their offsets (e.g. collection.usdz or collection.usd; "
        "requires the [usd] extra). A visual assembly only — no aggregate "
        "acoustics. Recorded as 'combined_usd_ref' in the manifest (relative to "
        "the manifest directory).",
    )
    # Reused placement flags — identical semantics to `place`.
    p.add_argument(
        "--algorithm",
        choices=["vbap", "dbap", "wfs", "ambisonics"],
        required=False,
        default="vbap",
        help="Placement algorithm applied per room (default: vbap).",
    )
    p.add_argument(
        "--n-speakers", type=int, default=8, metavar="N", help="Number of speakers."
    )
    p.add_argument(
        "--order",
        type=int,
        choices=[1, 2, 3],
        default=None,
        metavar="N",
        help="Ambisonics decode order (1|2|3); required for --algorithm "
        "ambisonics. EXPERIMENTAL (rig coordinates only; SH decode/route is "
        "engine-gated and UNCONFIRMED).",
    )
    p.add_argument(
        "--layout-radius",
        type=float,
        default=2.0,
        metavar="R",
        help="VBAP ring/dome radius in metres (default 2.0).",
    )
    p.add_argument(
        "--el-deg",
        type=float,
        default=0.0,
        metavar="E",
        help="VBAP elevation in degrees (default 0.0).",
    )
    p.add_argument(
        "--wfs-f-max-hz",
        type=float,
        default=8000.0,
        metavar="F",
        help="Highest reproduction frequency for WFS spatial-aliasing bound (default 8000.0).",
    )
    p.add_argument(
        "--wfs-spacing-m",
        type=float,
        default=None,
        metavar="S",
        help="Override per-speaker spacing in metres "
        "(default: derived from --layout-radius and --n-speakers).",
    )
    p.add_argument(
        "--out-dir",
        default=".",
        metavar="DIR",
        help="Output directory (default: cwd).",
    )


def _add_structure_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Additive `structure` subcommand (ADR 0050, Phase S1).

    Splits ONE real Apple RoomPlan ``CapturedStructure`` JSON export into N
    single-room ``RoomModel`` (one per ``section``) by the documented
    nearest-section-center wall HEURISTIC, then feeds them into the SAME
    composition path ``collection`` uses (per-room placement + per-room
    ``room.<name>.yaml`` / ``layout.<name>.yaml`` + a ``collection.yaml``
    manifest). The per-room split is a RECONSTRUCTION, not Apple-authoritative —
    see ``ROOMPLAN_STRUCTURE_SPLIT_NOTE``. NO aggregate footprint/volume/RT60.
    """
    p = sub.add_parser(
        "structure",
        help="Split a RoomPlan CapturedStructure export into a per-room collection.",
    )
    p.add_argument(
        "--in-structure",
        required=True,
        metavar="PATH",
        help="A RoomPlan CapturedStructure .json export (real device scan).",
    )
    p.add_argument(
        "--name",
        default="structure",
        metavar="NAME",
        help="Collection/venue name (no geometric meaning; default: 'structure').",
    )
    p.add_argument(
        "--combined-gltf",
        default=None,
        metavar="PATH",
        help="Optional path to write ONE combined glTF/GLB visual assembly of "
        "the per-room models (e.g. structure.glb). A visual assembly only — no "
        "aggregate acoustics; rooms are at their own local origin (no inter-room "
        "pose is inferred). Recorded as 'combined_ref' in the manifest.",
    )
    p.add_argument(
        "--combined-usd",
        default=None,
        metavar="PATH",
        help="Optional path to write ONE combined USD visual assembly of the "
        "per-room models (e.g. structure.usdz or structure.usd; requires the "
        "[usd] extra). A visual assembly only — no aggregate acoustics. Recorded "
        "as 'combined_usd_ref' in the manifest.",
    )
    # Reused placement flags — identical semantics to `place` / `collection`.
    p.add_argument(
        "--algorithm",
        choices=["vbap", "dbap", "wfs", "ambisonics"],
        required=False,
        default="vbap",
        help="Placement algorithm applied per room (default: vbap).",
    )
    p.add_argument(
        "--n-speakers", type=int, default=8, metavar="N", help="Number of speakers."
    )
    p.add_argument(
        "--order",
        type=int,
        choices=[1, 2, 3],
        default=None,
        metavar="N",
        help="Ambisonics decode order (1|2|3); required for --algorithm "
        "ambisonics. EXPERIMENTAL (rig coordinates only; SH decode/route is "
        "engine-gated and UNCONFIRMED).",
    )
    p.add_argument(
        "--layout-radius",
        type=float,
        default=2.0,
        metavar="R",
        help="VBAP ring/dome radius in metres (default 2.0).",
    )
    p.add_argument(
        "--el-deg",
        type=float,
        default=0.0,
        metavar="E",
        help="VBAP elevation in degrees (default 0.0).",
    )
    p.add_argument(
        "--wfs-f-max-hz",
        type=float,
        default=8000.0,
        metavar="F",
        help="Highest reproduction frequency for WFS spatial-aliasing bound (default 8000.0).",
    )
    p.add_argument(
        "--wfs-spacing-m",
        type=float,
        default=None,
        metavar="S",
        help="Override per-speaker spacing in metres "
        "(default: derived from --layout-radius and --n-speakers).",
    )
    p.add_argument(
        "--out-dir",
        default=".",
        metavar="DIR",
        help="Output directory (default: cwd).",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="roomestim",
        description="Room scan -> RoomModel + speaker placement -> spatial_engine YAMLs.",
    )
    parser.add_argument("--version", action="version", version=f"roomestim {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    _add_ingest_parser(sub)
    _add_place_parser(sub)
    _add_export_parser(sub)
    _add_run_parser(sub)
    _add_edit_parser(sub)
    _add_collection_parser(sub)
    _add_structure_parser(sub)

    return parser


# --------------------------------------------------------------------------- #
# Adapter factory
# --------------------------------------------------------------------------- #


class _ExperimentalGate(Exception):
    """Raised when --backend image is used without --experimental.

    Carries exit code 1 + a stderr message; handled before any torch/adapter
    construction so the gated-out image path stays torch-free.
    """


def _get_adapter(args: argparse.Namespace) -> "CaptureAdapter":
    backend: str = args.backend
    floor_reconstruction: str | None = getattr(args, "floor_reconstruction", None)
    if backend == "roomplan":
        from roomestim.adapters.roomplan import RoomPlanAdapter

        if floor_reconstruction in ("concave", "occupancy", "auto"):
            print(
                f"NOTE: --floor-reconstruction {floor_reconstruction} is ignored "
                f"for --backend {backend} (mesh-only; the RoomPlan footprint "
                f"comes from the capture sidecar polygon, not mesh extraction).",
                file=sys.stderr,
            )
        return RoomPlanAdapter()
    if backend == "polycam":
        from roomestim.adapters.polycam import PolycamAdapter

        if floor_reconstruction == "concave":
            print(
                "NOTE: concave footprint is a STRUCTURAL estimate; accuracy is "
                "UNVALIDATED (no footprint ground truth, ADR 0042).",
                file=sys.stderr,
            )
        elif floor_reconstruction == "occupancy":
            print(
                "NOTE: occupancy footprint is a ROBUSTNESS lever (density + "
                "connectivity rejects floaters); accuracy is UNVALIDATED as a "
                "default — single-scene (n=1) Redwood evidence, NOT an accuracy "
                "guarantee.",
                file=sys.stderr,
            )
        elif floor_reconstruction == "auto":
            from roomestim.adapters.mesh import AUTO_FLOOR_RECON_NOTE

            print(f"NOTE: {AUTO_FLOOR_RECON_NOTE}", file=sys.stderr)
        from roomestim.adapters.mesh import FloorReconstruction

        return PolycamAdapter(
            floor_reconstruction=cast("FloorReconstruction | None", floor_reconstruction)
        )
    if backend == "image":
        if floor_reconstruction in ("concave", "occupancy", "auto"):
            print(
                f"NOTE: --floor-reconstruction {floor_reconstruction} is ignored "
                f"for --backend {backend} (mesh-only; the image backend is its "
                f"own single-panorama tier, not mesh extraction).",
                file=sys.stderr,
            )
        # HARD GATE (ADR 0045): experimental rough-estimate tier. Fires BEFORE
        # constructing the adapter so no torch import happens on this path.
        if not getattr(args, "experimental", False):
            raise _ExperimentalGate(
                "--backend image is experimental (rough-estimate tier, not "
                "install-grade); pass --experimental to use it."
            )
        # Importing the module is torch-free (torch is lazy inside parse()).
        from roomestim.adapters.image import ImageAdapter

        return ImageAdapter(
            weights=getattr(args, "weights", "st3d"),
            accept_noncommercial=getattr(args, "accept_zind_tou", False),
        )
    raise ValueError(f"unknown backend: {backend!r}")


def _scale_anchor_for(args: argparse.Namespace) -> "ScaleAnchor | None":
    """Build a metric ScaleAnchor from --cam-height for --backend image.

    Returns None when no --cam-height is given (the image adapter then warns +
    falls back to its default camera height). Measured backends pass None too.
    """
    if getattr(args, "backend", None) != "image":
        return None
    cam_height = getattr(args, "cam_height", None)
    if cam_height is None:
        return None
    from roomestim.adapters.base import ScaleAnchor

    return ScaleAnchor("known_distance", cam_height)


def _maybe_print_estimated_notice(room: RoomModel) -> None:
    """Print the ESTIMATED provenance disclosure for image-reconstructed rooms.

    Measured backends (roomplan/polycam) emit provenance != "reconstructed", so
    nothing is printed for them.
    """
    if getattr(room, "provenance", None) == "reconstructed":
        print(
            "NOTE: geometry is ESTIMATED from a single image "
            "(provenance=reconstructed) — rough-estimate tier, NOT install-grade. "
            "Dimensions are approximate; verify before install. <=15 cm accuracy "
            "is reserved for LiDAR/RoomPlan capture.",
            file=sys.stderr,
        )


def _maybe_print_low_ceiling_notice(room: RoomModel) -> None:
    """Warn (stderr) when the measured ceiling height may be UNDER-reported.

    Fires only on ``ceiling_confidence == "low"`` (measured/mesh path). The
    threshold behind the flag is a HEURISTIC, not a calibrated probability —
    stated in the message. Not mutually exclusive with the reconstructed notice;
    called at the same sites.
    """
    if getattr(room, "ceiling_confidence", "unknown") == "low":
        coverage = getattr(room, "ceiling_coverage", None)
        coverage_str = f"{coverage:.0%}" if coverage is not None else "an unknown share"
        print(
            "NOTE: ceiling height may be UNDER-reported — the detected ceiling "
            f"plane covers only {coverage_str} of the floor footprint (heuristic "
            "threshold 50%). A tabletop, mezzanine slab, or under-sampled ceiling "
            "may have been mis-picked. Verify ceiling height before install. "
            "(ceiling_confidence=low, HEURISTIC not calibrated.)",
            file=sys.stderr,
        )


def _maybe_print_ambisonics_notes(args: argparse.Namespace) -> None:
    """Warn + disclose for ``--algorithm ambisonics`` (ADR 0041 §D-3a point 2).

    (a) WARN (NOT silent, D-5) when VBAP-only knobs (--el-deg / --n-speakers)
        were supplied — they are ignored for ambisonics (rig geometry is fixed
        by --order). (b) ALWAYS print the load-bearing AMBISONICS_RIG_DISCLOSURE
        so the engine-gated/UNCONFIRMED end-to-end status is unavoidable.
    """
    if getattr(args, "algorithm", None) != "ambisonics":
        return
    from roomestim.place.ambisonics import AMBISONICS_RIG_DISCLOSURE

    el_deg = getattr(args, "el_deg", 0.0)
    n_speakers = getattr(args, "n_speakers", 8)
    if el_deg != 0.0 or n_speakers != 8:
        print(
            "WARNING: --el-deg/--n-speakers are ignored for ambisonics; rig "
            "geometry is fixed by --order.",
            file=sys.stderr,
        )
    print(f"NOTE: {AMBISONICS_RIG_DISCLOSURE}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Placement dispatch
# --------------------------------------------------------------------------- #


def _run_placement(
    room: RoomModel,
    algorithm: str,
    n_speakers: int,
    layout_radius: float,
    el_deg: float,
    wfs_f_max_hz: float = 8000.0,
    wfs_spacing_m: float | None = None,
    order: int | None = None,
) -> PlacementResult:
    """Delegate to roomestim.place.dispatch.run_placement."""
    from roomestim.place.dispatch import run_placement

    result = run_placement(
        room, algorithm, n_speakers, layout_radius, el_deg,
        wfs_f_max_hz=wfs_f_max_hz, wfs_spacing_m=wfs_spacing_m,
        order=order,
    )
    # OQ-54 / ADR 0046: carry the room's capture provenance onto the placement so
    # the layout.yaml artifact reflects the geometry it was derived from. Single
    # point covering both _cmd_run and _cmd_place. PlacementResult is non-frozen.
    result.geometry_provenance = room.provenance
    return result


# --------------------------------------------------------------------------- #
# Sub-command implementations
# --------------------------------------------------------------------------- #


def _cmd_ingest(args: argparse.Namespace) -> int:
    from roomestim.export.room_yaml import write_room_yaml

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    octave_band: bool = getattr(args, "octave_band", False)
    adapter = _get_adapter(args)
    room = adapter.parse(
        Path(args.input),
        scale_anchor=_scale_anchor_for(args),
        octave_band=octave_band,
    )

    out_path = out_dir / "room.yaml"
    write_room_yaml(room, out_path)
    print(f"wrote {out_path}")
    _maybe_print_estimated_notice(room)
    _maybe_print_low_ceiling_notice(room)
    return 0


def _cmd_place(args: argparse.Namespace) -> int:
    from roomestim.export.layout_yaml import write_layout_yaml
    from roomestim.io.room_yaml_reader import read_room_yaml
    from roomestim.model import PlacementResult

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    room = read_room_yaml(args.in_room)
    _maybe_print_ambisonics_notes(args)
    result = _run_placement(
        room,
        args.algorithm,
        args.n_speakers,
        args.layout_radius,
        args.el_deg,
        wfs_f_max_hz=getattr(args, "wfs_f_max_hz", 8000.0),
        wfs_spacing_m=getattr(args, "wfs_spacing_m", None),
        order=getattr(args, "order", None),
    )
    assert isinstance(result, PlacementResult)

    out_path = out_dir / "layout.yaml"
    write_layout_yaml(result, out_path)
    print(f"wrote {out_path}")
    if getattr(args, "check_angles", False):
        _emit_layout_angle_check(result, room, out_dir)
    _maybe_print_estimated_notice(room)
    _maybe_print_low_ceiling_notice(room)
    return 0


def _emit_layout_angle_check(
    result: PlacementResult, room: RoomModel, out_dir: Path
) -> None:
    """Print the geometric layout-angle check + write the JSON sidecar.

    Listener point = the room's listener-area centroid (honest default). This is
    a geometry-only check; see ``LAYOUT_ANGLE_CHECK_NOTE``. It never mutates
    ``result`` or ``layout.yaml``.
    """
    import json

    from roomestim.model import Point3
    from roomestim.place.standards import (
        check_layout_angles,
        compute_layout_metrics,
        format_metrics_lines,
        format_report_lines,
        metrics_to_dict,
        report_to_dict,
    )

    centroid = room.listener_area.centroid
    listener = Point3(
        x=centroid.x, y=room.listener_area.height_m, z=centroid.z
    )
    report = check_layout_angles(result, listener=listener)
    for line in format_report_lines(report):
        print(line)
    metrics = compute_layout_metrics(result, listener=listener)
    for line in format_metrics_lines(metrics):
        print(line)
    sidecar_dict = report_to_dict(report)
    sidecar_dict["geometric_metrics"] = metrics_to_dict(metrics)
    sidecar = out_dir / "layout.angles.json"
    sidecar.write_text(
        json.dumps(sidecar_dict, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {sidecar}")


def _cmd_export(args: argparse.Namespace) -> int:
    from roomestim.io.placement_yaml_reader import read_placement_yaml
    from roomestim.io.room_yaml_reader import read_room_yaml

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    room = read_room_yaml(args.in_room)
    placement = read_placement_yaml(args.in_placement)

    export_format: str = getattr(args, "format", "yaml")
    with_acoustics_sidecar: bool = getattr(args, "with_acoustics_sidecar", False)

    if export_format == "yaml":
        from roomestim.export.layout_yaml import write_layout_yaml
        from roomestim.export.room_yaml import write_room_yaml

        room_out = out_dir / "room.yaml"
        layout_out = out_dir / "layout.yaml"

        write_room_yaml(room, room_out)

        # OQ-54 / ADR 0046: the room is authoritative for capture provenance, so
        # override the placement's marker before writing the layout.yaml artifact.
        placement.geometry_provenance = room.provenance

        # D42 precedence: CLI flag > ENV var > default ON (backward-compat).
        no_validation: bool = getattr(args, "no_engine_validation", False)
        cli_engine_path: str | None = getattr(args, "validate_engine", None)
        write_layout_yaml(
            placement,
            layout_out,
            validate=not no_validation,
            schema_path_override=cli_engine_path,
        )

        print(f"wrote {room_out}")
        print(f"wrote {layout_out}")
        return 0

    if export_format == "usdz":
        from roomestim.export.usd import write_usdz

        out_path = out_dir / "room.usdz"
        write_usdz(
            room,
            placement,
            out_path,
            with_acoustics_sidecar=with_acoustics_sidecar,
        )
        print(f"wrote {out_path}")
        return 0

    if export_format in ("gltf", "glb"):
        from roomestim.export.gltf import write_gltf

        out_path = out_dir / f"room.{export_format}"
        gltf_format: Literal["gltf", "glb"] = "glb" if export_format == "glb" else "gltf"
        write_gltf(
            room,
            placement,
            out_path,
            format=gltf_format,
            with_acoustics_sidecar=with_acoustics_sidecar,
        )
        print(f"wrote {out_path}")
        return 0

    raise ValueError(f"unknown export format: {export_format!r}")


def _cmd_run(args: argparse.Namespace) -> int:
    from roomestim.export.layout_yaml import write_layout_yaml
    from roomestim.export.room_yaml import write_room_yaml
    from roomestim.model import PlacementResult

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    octave_band: bool = getattr(args, "octave_band", False)
    adapter = _get_adapter(args)
    room = adapter.parse(
        Path(args.input),
        scale_anchor=_scale_anchor_for(args),
        octave_band=octave_band,
    )

    _maybe_print_ambisonics_notes(args)
    result = _run_placement(
        room,
        args.algorithm,
        args.n_speakers,
        args.layout_radius,
        args.el_deg,
        wfs_f_max_hz=getattr(args, "wfs_f_max_hz", 8000.0),
        wfs_spacing_m=getattr(args, "wfs_spacing_m", None),
        order=getattr(args, "order", None),
    )
    assert isinstance(result, PlacementResult)

    room_out = out_dir / "room.yaml"
    layout_out = out_dir / "layout.yaml"

    write_room_yaml(room, room_out)

    # FIX-4 / D77: D42 precedence — CLI flag > ENV var > default ON.
    no_validation: bool = getattr(args, "no_engine_validation", False)
    cli_engine_path: str | None = getattr(args, "validate_engine", None)
    write_layout_yaml(
        result,
        layout_out,
        validate=not no_validation,
        schema_path_override=cli_engine_path,
    )

    print(f"wrote {room_out}")
    print(f"wrote {layout_out}")
    _maybe_print_estimated_notice(room)
    _maybe_print_low_ceiling_notice(room)
    return 0


def _cmd_edit(args: argparse.Namespace) -> int:
    import difflib

    from roomestim.edit import nudge_speaker
    from roomestim.export.layout_yaml import validate_placement, write_layout_yaml
    from roomestim.io.placement_yaml_reader import read_placement_yaml

    placement = read_placement_yaml(args.in_placement)
    before = Path(args.in_placement).read_text(encoding="utf-8")

    # Flag→kwarg map (Fix 2): --daz→daz_deg, --del-deg→del_deg, --ddist→ddist_m,
    # --dx/--dy/--dz→dx/dy/dz. ValueError (frame mixing / dist<=0) and IndexError
    # (speaker out of range) propagate to main() → exit 1.
    edited = nudge_speaker(
        placement,
        args.speaker,
        daz_deg=args.daz,
        del_deg=args.del_deg,
        ddist_m=args.ddist,
        dx=args.dx,
        dy=args.dy,
        dz=args.dz,
    )

    no_val: bool = getattr(args, "no_engine_validation", False)
    cli_path: str | None = getattr(args, "validate_engine", None)
    if not no_val:
        errs = validate_placement(edited, schema_path_override=cli_path)
        if errs:
            for e in errs:
                print(f"error: {e}", file=sys.stderr)
            return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "layout.yaml"
    write_layout_yaml(
        edited, out_path, validate=not no_val, schema_path_override=cli_path
    )
    after = out_path.read_text(encoding="utf-8")

    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=str(args.in_placement),
        tofile=str(out_path),
    )
    sys.stdout.writelines(diff)
    print(f"wrote {out_path}")
    return 0


def _unique_room_slug(name: str, used_slugs: set[str]) -> str:
    """Return a filesystem-safe, collision-free slug for ``name`` (Risk #4).

    Sanitizes characters outside ``[A-Za-z0-9._-]`` to ``_`` (avoids path
    separators leaking into per-room filenames), then deterministically
    index-suffixes (``-1``, ``-2``, ...) until the slug is unused. ``used_slugs``
    is mutated to record the returned slug.
    """
    import re

    base = re.sub(r"[^A-Za-z0-9._-]", "_", name) or "room"
    candidate = base
    i = 0
    while candidate in used_slugs:
        i += 1
        candidate = f"{base}-{i}"
    used_slugs.add(candidate)
    return candidate


def _parse_offsets(
    offsets_arg: list[str] | None, n_rooms: int
) -> list[tuple[float, float, float] | None]:
    """Parse the optional ``--offsets`` flag into a parallel-indexed list.

    Each token is ``"X,Y,Z"`` (metres). ``None`` (flag absent) ⇒ all-identity.
    The count must match the number of rooms; offsets are USER-SUPPLIED only —
    roomestim never infers inter-room pose.
    """
    if offsets_arg is None:
        return [None] * n_rooms
    if len(offsets_arg) != n_rooms:
        raise ValueError(
            f"--offsets must have one 'X,Y,Z' per room: got {len(offsets_arg)} "
            f"offsets for {n_rooms} --in-rooms."
        )
    parsed: list[tuple[float, float, float] | None] = []
    for tok in offsets_arg:
        parts = tok.split(",")
        if len(parts) != 3:
            raise ValueError(
                f"--offsets entry must be 'X,Y,Z' (3 comma-separated metres), "
                f"got {tok!r}."
            )
        try:
            x, y, z = (float(parts[0]), float(parts[1]), float(parts[2]))
        except ValueError as exc:
            raise ValueError(
                f"--offsets entry {tok!r} has a non-numeric component."
            ) from exc
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            raise ValueError(
                f"--offsets entry {tok!r} has a non-finite (NaN/inf) component; "
                "offsets must be finite metres."
            )
        parsed.append((x, y, z))
    return parsed


def _cmd_collection(args: argparse.Namespace) -> int:
    import os

    from roomestim.collection import RoomCollection
    from roomestim.export.collection_yaml import write_collection_yaml
    from roomestim.export.layout_yaml import write_layout_yaml
    from roomestim.export.room_yaml import write_room_yaml
    from roomestim.io.room_yaml_reader import read_room_yaml
    from roomestim.model import PlacementResult

    in_rooms: list[str] = args.in_rooms
    if len(in_rooms) < 2:
        raise ValueError(
            "collection requires at least 2 --in-rooms inputs "
            f"(got {len(in_rooms)}); a collection is an ordered bundle of N "
            "explicit single-room captures."
        )

    offsets = _parse_offsets(getattr(args, "offsets", None), len(in_rooms))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _maybe_print_ambisonics_notes(args)

    rooms: list[RoomModel] = []
    placements: list[PlacementResult | None] = []
    room_refs: list[str] = []
    layout_refs: list[str | None] = []
    used_slugs: set[str] = set()

    for in_room in in_rooms:
        room = read_room_yaml(in_room)
        # Same library path as _cmd_place: read_room_yaml -> run_placement ->
        # write_layout_yaml. _cmd_place itself is NOT called/edited.
        result = _run_placement(
            room,
            args.algorithm,
            args.n_speakers,
            args.layout_radius,
            args.el_deg,
            wfs_f_max_hz=getattr(args, "wfs_f_max_hz", 8000.0),
            wfs_spacing_m=getattr(args, "wfs_spacing_m", None),
            order=getattr(args, "order", None),
        )
        assert isinstance(result, PlacementResult)

        slug = _unique_room_slug(room.name, used_slugs)
        room_ref = f"room.{slug}.yaml"
        layout_ref = f"layout.{slug}.yaml"
        write_room_yaml(room, out_dir / room_ref)
        write_layout_yaml(result, out_dir / layout_ref)
        print(f"wrote {out_dir / room_ref}")
        print(f"wrote {out_dir / layout_ref}")
        _maybe_print_estimated_notice(room)
        _maybe_print_low_ceiling_notice(room)

        rooms.append(room)
        placements.append(result)
        room_refs.append(room_ref)
        layout_refs.append(layout_ref)

    collection = RoomCollection(
        name=args.name, rooms=rooms, placements=placements, offsets=offsets
    )

    combined_ref: str | None = None
    combined_gltf = getattr(args, "combined_gltf", None)
    if combined_gltf:
        from roomestim.export.collection_gltf import write_collection_gltf

        combined_path = Path(combined_gltf)
        fmt: Literal["gltf", "glb"] = (
            "gltf" if combined_path.suffix.lower() == ".gltf" else "glb"
        )
        write_collection_gltf(collection, combined_path, format=fmt)
        print(f"wrote {combined_path}")
        # Record relative to the manifest dir (no absolute path leaks).
        combined_ref = os.path.relpath(combined_path, out_dir)
        if any(o is None for o in offsets):
            print(
                "note: combined glTF is a visual assembly only; rooms without a "
                "user-supplied --offset are emitted at their local origin "
                "(they may overlap). roomestim does not infer inter-room pose."
            )

    combined_usd_ref: str | None = None
    combined_usd = getattr(args, "combined_usd", None)
    if combined_usd:
        from roomestim.export.collection_usd import write_collection_usd

        combined_usd_path = Path(combined_usd)
        write_collection_usd(collection, combined_usd_path)
        print(f"wrote {combined_usd_path}")
        # Record relative to the manifest dir (no absolute path leaks).
        combined_usd_ref = os.path.relpath(combined_usd_path, out_dir)
        if any(o is None for o in offsets):
            print(
                "note: combined USD is a visual assembly only; rooms without a "
                "user-supplied --offset are emitted at their local origin "
                "(they may overlap). roomestim does not infer inter-room pose."
            )

    manifest_path = out_dir / "collection.yaml"
    write_collection_yaml(
        collection,
        manifest_path,
        room_refs=room_refs,
        layout_refs=layout_refs,
        combined_ref=combined_ref,
        combined_usd_ref=combined_usd_ref,
    )
    print(f"wrote {manifest_path}")
    return 0


def _cmd_structure(args: argparse.Namespace) -> int:
    """Split a RoomPlan CapturedStructure into a per-room collection (ADR 0050).

    Mirrors ``_cmd_collection``: ``parse_structure`` -> N RoomModel -> per-room
    ``_run_placement`` (the SAME library path ``place`` uses) -> per-room
    ``room.<slug>.yaml`` / ``layout.<slug>.yaml`` -> ``RoomCollection`` ->
    ``collection.yaml``. The per-room split is a HEURISTIC reconstruction; the
    disclosure note is printed so it is unavoidable.
    """
    import os

    from roomestim.adapters.roomplan_structure import parse_structure
    from roomestim.collection import RoomCollection
    from roomestim.export.collection_yaml import write_collection_yaml
    from roomestim.export.layout_yaml import write_layout_yaml
    from roomestim.export.room_yaml import write_room_yaml
    from roomestim.model import PlacementResult
    from roomestim.reconstruct._disclosure import ROOMPLAN_STRUCTURE_SPLIT_NOTE

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rooms = parse_structure(Path(args.in_structure))

    print(f"NOTE: {ROOMPLAN_STRUCTURE_SPLIT_NOTE}", file=sys.stderr)
    _maybe_print_ambisonics_notes(args)

    placements: list[PlacementResult | None] = []
    room_refs: list[str] = []
    layout_refs: list[str | None] = []
    used_slugs: set[str] = set()

    for room in rooms:
        # Same library path as _cmd_place / _cmd_collection: run_placement ->
        # write_layout_yaml. _cmd_place itself is NOT called/edited.
        result = _run_placement(
            room,
            args.algorithm,
            args.n_speakers,
            args.layout_radius,
            args.el_deg,
            wfs_f_max_hz=getattr(args, "wfs_f_max_hz", 8000.0),
            wfs_spacing_m=getattr(args, "wfs_spacing_m", None),
            order=getattr(args, "order", None),
        )
        assert isinstance(result, PlacementResult)

        slug = _unique_room_slug(room.name, used_slugs)
        room_ref = f"room.{slug}.yaml"
        layout_ref = f"layout.{slug}.yaml"
        write_room_yaml(room, out_dir / room_ref)
        write_layout_yaml(result, out_dir / layout_ref)
        print(f"wrote {out_dir / room_ref}")
        print(f"wrote {out_dir / layout_ref}")

        placements.append(result)
        room_refs.append(room_ref)
        layout_refs.append(layout_ref)

    collection = RoomCollection(name=args.name, rooms=rooms, placements=placements)

    # Optional combined visual assembly — REUSES the shipped ADR 0049 collection
    # writers (no offsets => rooms at their own local origin; honest note below).
    combined_ref: str | None = None
    combined_gltf = getattr(args, "combined_gltf", None)
    if combined_gltf:
        from roomestim.export.collection_gltf import write_collection_gltf

        combined_path = Path(combined_gltf)
        fmt: Literal["gltf", "glb"] = (
            "gltf" if combined_path.suffix.lower() == ".gltf" else "glb"
        )
        write_collection_gltf(collection, combined_path, format=fmt)
        print(f"wrote {combined_path}")
        combined_ref = os.path.relpath(combined_path, out_dir)
        print(
            "note: combined glTF is a visual assembly only; rooms are emitted at "
            "their local origin (they may overlap). roomestim does not infer "
            "inter-room pose."
        )

    combined_usd_ref: str | None = None
    combined_usd = getattr(args, "combined_usd", None)
    if combined_usd:
        from roomestim.export.collection_usd import write_collection_usd

        combined_usd_path = Path(combined_usd)
        write_collection_usd(collection, combined_usd_path)
        print(f"wrote {combined_usd_path}")
        combined_usd_ref = os.path.relpath(combined_usd_path, out_dir)
        print(
            "note: combined USD is a visual assembly only; rooms are emitted at "
            "their local origin (they may overlap). roomestim does not infer "
            "inter-room pose."
        )

    manifest_path = out_dir / "collection.yaml"
    write_collection_yaml(
        collection,
        manifest_path,
        room_refs=room_refs,
        layout_refs=layout_refs,
        combined_ref=combined_ref,
        combined_usd_ref=combined_usd_ref,
    )
    print(f"wrote {manifest_path}")
    return 0


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "ingest":
            return _cmd_ingest(args)
        if args.command == "place":
            return _cmd_place(args)
        if args.command == "export":
            return _cmd_export(args)
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "edit":
            return _cmd_edit(args)
        if args.command == "collection":
            return _cmd_collection(args)
        if args.command == "structure":
            return _cmd_structure(args)
    except _ExperimentalGate as gate:
        print(f"error: {gate}", file=sys.stderr)
        return 1
    except (ValueError, OSError, RuntimeError, IndexError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"unknown command: {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
