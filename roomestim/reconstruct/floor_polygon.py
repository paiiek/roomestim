"""Mesh -> 2D floor polygon reconstruction.

P4 ships only the RoomPlan sidecar path, which already provides a parametric
floor polygon. The mesh-based reconstruction (Polycam OBJ) lands in P5 via
alpha-shape over floor-projected vertices.
"""

from __future__ import annotations

import numpy as np

from roomestim.model import Point2

__all__ = ["floor_polygon_from_mesh"]


def floor_polygon_from_mesh(mesh_vertices: np.ndarray) -> list[Point2]:
    """Reconstruct a 2D floor polygon from a 3D mesh vertex cloud.

    Reserved for the P5 Polycam path. v0.1 P4 does not exercise this code
    path because the RoomPlan sidecar provides the floor polygon directly.

    Parameters
    ----------
    mesh_vertices:
        ``(N, 3)`` array of mesh vertex positions in listener-frame metres.

    Returns
    -------
    list[Point2]
        CCW floor polygon.

    Raises
    ------
    NotImplementedError
        Always, in v0.1 P4. Implementation lands in P5.
    """
    del mesh_vertices  # unused in stub
    raise NotImplementedError(
        "floor_polygon_from_mesh is planned for P5 (Polycam adapter); "
        "v0.1 P4 sidecar path does not invoke this code."
    )
