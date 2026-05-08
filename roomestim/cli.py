"""CLI entry point for roomestim.

Subcommands
-----------
ingest  -- parse a capture artifact into a RoomModel; write room.yaml
place   -- load room.yaml, run placement, write layout.yaml
export  -- re-emit room.yaml + layout.yaml (idempotent)
run     -- composite: ingest + place + export
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from roomestim import __version__


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

    return parser


# --------------------------------------------------------------------------- #
# Adapter factory
# --------------------------------------------------------------------------- #


def _get_adapter(backend: str) -> object:
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
    room: object,
    algorithm: str,
    n_speakers: int,
    layout_radius: float,
    el_deg: float,
    wfs_f_max_hz: float = 8000.0,
    wfs_spacing_m: float | None = None,
) -> object:
    """Dispatch to the right placement function and return a PlacementResult."""
    from roomestim.model import RoomModel, Surface

    assert isinstance(room, RoomModel)

    if algorithm == "vbap":
        from roomestim.place.vbap import place_vbap_ring

        return place_vbap_ring(n_speakers, radius_m=layout_radius, el_deg=el_deg)

    if algorithm == "dbap":
        from roomestim.place.dbap import place_dbap

        mount_surfaces: list[Surface] = [
            s for s in room.surfaces if s.kind in ("wall", "ceiling")
        ]
        if not mount_surfaces:
            raise ValueError(
                "DBAP placement requires at least one wall or ceiling surface; "
                "none found in room.yaml."
            )
        return place_dbap(
            mount_surfaces=mount_surfaces,
            n_speakers=n_speakers,
            listener_area=room.listener_area,
        )

    if algorithm == "wfs":
        import math

        from roomestim.model import Point2
        from roomestim.place.wfs import c as wfs_c
        from roomestim.place.wfs import place_wfs

        p0 = Point2(x=-layout_radius, z=layout_radius)
        p1 = Point2(x=layout_radius, z=layout_radius)
        baseline_len = abs(p1.x - p0.x)
        if wfs_spacing_m is not None:
            spacing_m = float(wfs_spacing_m)
        else:
            spacing_m = (
                baseline_len / max(n_speakers - 1, 1) if n_speakers > 1 else baseline_len
            )
        try:
            return place_wfs(
                baseline_p0=p0,
                baseline_p1=p1,
                spacing_m=spacing_m,
                f_max_hz=wfs_f_max_hz,
            )
        except ValueError as exc:
            # Re-raise with a constructive remediation message at the CLI layer.
            # Library-level place_wfs ValueError contract is unchanged.
            bound = wfs_c / (2.0 * wfs_f_max_hz)
            if spacing_m > bound:
                # Max safe f_max for the *current* (derived or supplied) spacing.
                max_safe_f_max = wfs_c / (2.0 * spacing_m)
                # Min safe n for the *current* f_max_hz, derived from baseline_len.
                # n - 1 >= baseline_len / bound = baseline_len * 2 * f_max / c.
                if baseline_len > 0.0:
                    min_safe_n = int(math.ceil(baseline_len / bound)) + 1
                else:
                    min_safe_n = n_speakers
                raise ValueError(
                    f"WFS spatial-aliasing bound violated: "
                    f"spacing_m={spacing_m:.4f} > c/(2*f_max_hz)={bound:.4f} "
                    f"(c=343.0 m/s, f_max_hz={wfs_f_max_hz}). "
                    f"Either pass --wfs-f-max-hz <X> "
                    f"(max safe --wfs-f-max-hz for current spacing is "
                    f"X = c/(2*spacing_m) = {max_safe_f_max:.2f} Hz) "
                    f"OR pass --n-speakers <Y> "
                    f"(minimum safe --n-speakers for current f_max_hz is "
                    f"Y = ceil(baseline_len/(c/(2*f_max))) + 1 = {min_safe_n})."
                ) from exc
            raise

    raise ValueError(f"unknown algorithm: {algorithm!r}")


# --------------------------------------------------------------------------- #
# Sub-command implementations
# --------------------------------------------------------------------------- #


def _cmd_ingest(args: argparse.Namespace) -> int:
    from roomestim.export.room_yaml import write_room_yaml
    from roomestim.model import RoomModel

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    octave_band: bool = getattr(args, "octave_band", False)
    adapter = _get_adapter(args.backend)
    parse = getattr(adapter, "parse")
    room = parse(args.input, scale_anchor=None, octave_band=octave_band)
    assert isinstance(room, RoomModel)

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
    from roomestim.export.layout_yaml import write_layout_yaml
    from roomestim.export.room_yaml import write_room_yaml
    from roomestim.io.placement_yaml_reader import read_placement_yaml
    from roomestim.io.room_yaml_reader import read_room_yaml

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    room = read_room_yaml(args.in_room)
    placement = read_placement_yaml(args.in_placement)

    room_out = out_dir / "room.yaml"
    layout_out = out_dir / "layout.yaml"

    write_room_yaml(room, room_out)
    write_layout_yaml(placement, layout_out)

    print(f"wrote {room_out}")
    print(f"wrote {layout_out}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from roomestim.export.layout_yaml import write_layout_yaml
    from roomestim.export.room_yaml import write_room_yaml
    from roomestim.model import PlacementResult, RoomModel

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    octave_band: bool = getattr(args, "octave_band", False)
    adapter = _get_adapter(args.backend)
    parse = getattr(adapter, "parse")
    room = parse(args.input, scale_anchor=None, octave_band=octave_band)
    assert isinstance(room, RoomModel)

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
    write_layout_yaml(result, layout_out)

    print(f"wrote {room_out}")
    print(f"wrote {layout_out}")
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
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"unknown command: {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
