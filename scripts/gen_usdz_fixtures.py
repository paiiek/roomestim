"""Generate Y-up and Z-up shoebox USDZ fixtures for MeshAdapter tests.

Builds a 4 x 3 x 2.5 m box (X=4, vertical=2.5, depth=3) as a single
UsdGeom.Mesh and packages it as .usdz. Two stages: one declares upAxis=Y
(vertical on local Y), the other upAxis=Z (vertical on local Z).
"""
from __future__ import annotations

import sys
from pathlib import Path

from pxr import Usd, UsdGeom, UsdUtils, Vt


def _box_points(up: str) -> list[tuple[float, float, float]]:
    # Footprint 4 (x) x 3 (depth) ; height 2.5 (vertical).
    fx, fd, h = 4.0, 3.0, 2.5
    if up == "Y":
        # vertical = Y ; horizontals X, Z(depth)
        lo, hi = 0.0, h
        base = [(0, lo, 0), (fx, lo, 0), (fx, lo, fd), (0, lo, fd)]
        top = [(0, hi, 0), (fx, hi, 0), (fx, hi, fd), (0, hi, fd)]
    else:  # "Z"
        # vertical = Z ; horizontals X, Y(depth)
        lo, hi = 0.0, h
        base = [(0, 0, lo), (fx, 0, lo), (fx, fd, lo), (0, fd, lo)]
        top = [(0, 0, hi), (fx, 0, hi), (fx, fd, hi), (0, fd, hi)]
    return [(float(a), float(b), float(c)) for (a, b, c) in base + top]


def _box_faces() -> tuple[list[int], list[int]]:
    # 6 quad faces of a box: bottom, top, 4 sides. Indices 0-3 base, 4-7 top.
    quads = [
        [0, 1, 2, 3],  # bottom
        [4, 7, 6, 5],  # top
        [0, 4, 5, 1],  # side
        [1, 5, 6, 2],
        [2, 6, 7, 3],
        [3, 7, 4, 0],
    ]
    counts = [4] * len(quads)
    indices: list[int] = []
    for q in quads:
        indices.extend(q)
    return counts, indices


def make(out: Path, up: str) -> None:
    stage = Usd.Stage.CreateInMemory()
    token = UsdGeom.Tokens.y if up == "Y" else UsdGeom.Tokens.z
    UsdGeom.SetStageUpAxis(stage, token)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    root = UsdGeom.Xform.Define(stage, "/Room")
    stage.SetDefaultPrim(root.GetPrim())
    mesh = UsdGeom.Mesh.Define(stage, "/Room/Box")
    pts = _box_points(up)
    counts, indices = _box_faces()
    mesh.CreatePointsAttr(Vt.Vec3fArray([tuple(p) for p in pts]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray(counts))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(indices))

    tmp = out.with_suffix(".usdc")
    stage.GetRootLayer().Export(str(tmp))
    try:
        UsdUtils.CreateNewUsdzPackage(str(tmp), str(out))
    finally:
        if tmp.exists():
            tmp.unlink()
    print(f"wrote {out} (upAxis={up}, {out.stat().st_size} bytes)")


if __name__ == "__main__":
    dst = Path(sys.argv[1])
    dst.mkdir(parents=True, exist_ok=True)
    make(dst / "shoebox_yup.usdz", "Y")
    make(dst / "shoebox_zup.usdz", "Z")
