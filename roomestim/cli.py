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
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from roomestim import __version__

if TYPE_CHECKING:
    from roomestim.adapters.base import CaptureAdapter
    from roomestim.model import PlacementResult, RoomModel


# --------------------------------------------------------------------------- #
# Argument parser helpers
# --------------------------------------------------------------------------- #


def _add_ingest_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("ingest", help="Parse a capture artifact into a RoomModel.")
    p.add_argument(
        "--backend",
        choices=["roomplan", "polycam"],
        required=True,
        help="Capture backend.",
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


def _add_place_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("place", help="Run speaker placement; write layout.yaml.")
    p.add_argument("--in-room", required=True, metavar="PATH", help="room.yaml path.")
    p.add_argument(
        "--algorithm",
        choices=["vbap", "dbap", "wfs"],
        required=True,
        help="Placement algorithm.",
    )
    p.add_argument(
        "--n-speakers", type=int, default=8, metavar="N", help="Number of speakers."
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
        choices=["roomplan", "polycam"],
        required=True,
        help="Capture backend.",
    )
    p.add_argument("--input", required=True, metavar="PATH", help="Input file path.")
    p.add_argument(
        "--algorithm",
        choices=["vbap", "dbap", "wfs"],
        required=True,
        help="Placement algorithm.",
    )
    p.add_argument(
        "--n-speakers", type=int, default=8, metavar="N", help="Number of speakers."
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

    return parser


# --------------------------------------------------------------------------- #
# Adapter factory
# --------------------------------------------------------------------------- #


def _get_adapter(backend: str) -> "CaptureAdapter":
    if backend == "roomplan":
        from roomestim.adapters.roomplan import RoomPlanAdapter

        return RoomPlanAdapter()
    if backend == "polycam":
        from roomestim.adapters.polycam import PolycamAdapter

        return PolycamAdapter()
    raise ValueError(f"unknown backend: {backend!r}")


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
) -> PlacementResult:
    """Delegate to roomestim.place.dispatch.run_placement."""
    from roomestim.place.dispatch import run_placement

    return run_placement(
        room, algorithm, n_speakers, layout_radius, el_deg,
        wfs_f_max_hz=wfs_f_max_hz, wfs_spacing_m=wfs_spacing_m,
    )


# --------------------------------------------------------------------------- #
# Sub-command implementations
# --------------------------------------------------------------------------- #


def _cmd_ingest(args: argparse.Namespace) -> int:
    from roomestim.export.room_yaml import write_room_yaml

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    octave_band: bool = getattr(args, "octave_band", False)
    adapter = _get_adapter(args.backend)
    room = adapter.parse(Path(args.input), scale_anchor=None, octave_band=octave_band)

    out_path = out_dir / "room.yaml"
    write_room_yaml(room, out_path)
    print(f"wrote {out_path}")
    return 0


def _cmd_place(args: argparse.Namespace) -> int:
    from roomestim.export.layout_yaml import write_layout_yaml
    from roomestim.io.room_yaml_reader import read_room_yaml
    from roomestim.model import PlacementResult

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    room = read_room_yaml(args.in_room)
    result = _run_placement(
        room,
        args.algorithm,
        args.n_speakers,
        args.layout_radius,
        args.el_deg,
        wfs_f_max_hz=getattr(args, "wfs_f_max_hz", 8000.0),
        wfs_spacing_m=getattr(args, "wfs_spacing_m", None),
    )
    assert isinstance(result, PlacementResult)

    out_path = out_dir / "layout.yaml"
    write_layout_yaml(result, out_path)
    print(f"wrote {out_path}")
    return 0


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
    adapter = _get_adapter(args.backend)
    room = adapter.parse(Path(args.input), scale_anchor=None, octave_band=octave_band)

    result = _run_placement(
        room,
        args.algorithm,
        args.n_speakers,
        args.layout_radius,
        args.el_deg,
        wfs_f_max_hz=getattr(args, "wfs_f_max_hz", 8000.0),
        wfs_spacing_m=getattr(args, "wfs_spacing_m", None),
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
    except (ValueError, OSError, RuntimeError, IndexError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"unknown command: {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
