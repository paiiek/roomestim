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
        from roomestim.model import Point2
        from roomestim.place.wfs import place_wfs

        p0 = Point2(x=-layout_radius, z=layout_radius)
        p1 = Point2(x=layout_radius, z=layout_radius)
        baseline_len = abs(p1.x - p0.x)
        spacing_m = baseline_len / max(n_speakers - 1, 1) if n_speakers > 1 else baseline_len
        f_max_hz = 8000.0
        return place_wfs(
            baseline_p0=p0,
            baseline_p1=p1,
            spacing_m=spacing_m,
            f_max_hz=f_max_hz,
        )

    raise ValueError(f"unknown algorithm: {algorithm!r}")


# --------------------------------------------------------------------------- #
# Sub-command implementations
# --------------------------------------------------------------------------- #


def _cmd_ingest(args: argparse.Namespace) -> int:
    from roomestim.export.room_yaml import write_room_yaml
    from roomestim.model import RoomModel

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    adapter = _get_adapter(args.backend)
    parse = getattr(adapter, "parse")
    room = parse(args.input, scale_anchor=None)
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
    result = _run_placement(room, args.algorithm, args.n_speakers, args.layout_radius, args.el_deg)
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

    adapter = _get_adapter(args.backend)
    parse = getattr(adapter, "parse")
    room = parse(args.input, scale_anchor=None)
    assert isinstance(room, RoomModel)

    result = _run_placement(room, args.algorithm, args.n_speakers, args.layout_radius, args.el_deg)
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
