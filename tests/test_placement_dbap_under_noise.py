"""Step 4 of v0.1.1 closeout — DBAP placement characterisation under noise.

DBAP's ``_greedy_max_min_select`` (``roomestim/place/dbap.py:215–247``) is
structurally discrete: argmax tie-break can flip the selected candidate set on
small input perturbation. Position drift is therefore non-smooth in σ and no
a-priori smooth bound exists. This module asserts ONLY the invariants we
actually own — non-divergence, on-surface, count preservation — and PRINTS a
diagnostic drift histogram (use ``pytest -s``) so reviewers can detect drift
regressions visually without locking a fabricated number.

Characterisation snapshot 2026-05-05 (sigma in cm; drift in m, n=600 = 6
speakers × 100 trials per σ; live values are re-printed by the diagnostic
block on every run — see ``pytest -s``):

    σ=0 cm: drift_mean≈0       wall_flip_rate≈[0,0,0,0,0,0]
    σ≥1 cm: drift_mean≈2.0 m   wall_flip_rate≈[~0.5 each]   (greedy bimodal flip)

The metres-scale drift at sub-cm wall noise is the non-smoothness flagged
in the plan — greedy argmax tie-break flips speakers to other walls of a
5×4 m shoebox under near-zero perturbation. The drift histogram alone
saturates as σ grows and cannot detect a stability regression
(e.g., a fix that made greedy more deterministic would still pass the
invariant test). The per-channel wall_flip_rate is the sharper signal —
a regression that changes which wall channel-i selects under perturbation
will show up as a per-channel rate change. The on-surface invariant still
holds at every σ. No a-priori bound is asserted on either metric.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from shapely.geometry import Point as ShapelyPoint

from roomestim.model import Point3, Surface
from roomestim.place.dbap import place_dbap
from tests.fixtures.synthetic_rooms import perturb_room_with_walls, shoebox

# Re-use the on-surface helpers from the existing DBAP tests so the
# characterisation reads from the same definition.
from tests.test_placement_dbap import (
    _is_on_any_surface,
    _project_point_to_surface_2d,
    _surface_polygon_2d,
    _wall_surfaces,
)


def _wall_index_for(point: Point3, walls: list[Surface], slack_m: float = 0.01) -> int:
    """Return the index of the wall whose plane+polygon ``point`` lies on.

    Picks the wall with the smallest absolute plane-distance among walls
    where the point projects inside the polygon (with ``slack_m`` slack).
    Returns -1 if no wall qualifies — this should not happen under the
    on-surface invariant, so a -1 in the histogram is itself a signal.
    """
    best_idx = -1
    best_abs_dist = float("inf")
    for idx, wall in enumerate(walls):
        u, v, dist_plane = _project_point_to_surface_2d(point, wall)
        if abs(dist_plane) >= best_abs_dist:
            continue
        if not _surface_polygon_2d(wall).buffer(slack_m).contains(ShapelyPoint(u, v)):
            continue
        best_idx = idx
        best_abs_dist = abs(dist_plane)
    return best_idx


SIGMAS_M = [0.00, 0.01, 0.02, 0.05]  # 0, 1, 2, 5 cm
N_TRIALS = 100
N_SPEAKERS = 6


def _drift_m(a: Point3, b: Point3) -> float:
    return math.sqrt(
        (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2
    )


@pytest.mark.parametrize("sigma_m", SIGMAS_M)
def test_dbap_invariants_under_noise(sigma_m: float, capsys: pytest.CaptureFixture[str]) -> None:
    """Invariant asserts (non-divergence, on-surface, count) + diagnostic histogram.

    For each σ in {0, 1, 2, 5} cm:
      1. Run 100 perturbation trials (seed = trial index).
      2. For every speaker on every trial: assert position is finite, lies
         on (or ≤1 cm of) at least one perturbed wall, and the result has
         exactly N_SPEAKERS speakers.
      3. Print per-σ drift histogram (mean, p50, p95, max) channel-matched
         to the σ=0 baseline.

    The drift histogram is NOT asserted; it is committed in the docstring
    above as a snapshot for visual regression review.
    """
    base_room = shoebox()
    base_walls = _wall_surfaces(base_room.surfaces)
    base_result = place_dbap(
        mount_surfaces=base_walls,
        n_speakers=N_SPEAKERS,
        listener_area=base_room.listener_area,
    )
    assert len(base_result.speakers) == N_SPEAKERS, (
        f"baseline returned {len(base_result.speakers)} speakers, expected {N_SPEAKERS}"
    )
    base_positions = [sp.position for sp in base_result.speakers]
    base_wall_idx = [_wall_index_for(p, base_walls) for p in base_positions]
    assert all(idx >= 0 for idx in base_wall_idx), (
        f"baseline wall_index lookup failed: {base_wall_idx}"
    )

    drifts: list[float] = []
    # Per-channel flip counter: flips[ch] = #trials where channel ch landed on
    # a different wall index than the baseline. Sharper than mean drift for
    # detecting greedy-selection regressions because it doesn't saturate.
    flips_per_channel = [0] * N_SPEAKERS
    for trial in range(N_TRIALS):
        perturbed = perturb_room_with_walls(base_room, sigma_m=sigma_m, seed=trial)
        walls = _wall_surfaces(perturbed.surfaces)
        result = place_dbap(
            mount_surfaces=walls,
            n_speakers=N_SPEAKERS,
            listener_area=perturbed.listener_area,
        )

        # --- Invariant 3: count preserved -------------------------------- #
        assert len(result.speakers) == N_SPEAKERS, (
            f"σ={sigma_m} m trial={trial}: returned {len(result.speakers)} "
            f"speakers, expected {N_SPEAKERS}"
        )

        for ch_i, (sp_base, sp) in enumerate(zip(base_positions, result.speakers)):
            # --- Invariant 1: non-divergence ----------------------------- #
            assert all(
                math.isfinite(c) for c in (sp.position.x, sp.position.y, sp.position.z)
            ), f"σ={sigma_m} m trial={trial} ch{sp.channel}: non-finite position {sp.position}"

            # --- Invariant 2: on-surface (≤1 cm slack) ------------------- #
            assert _is_on_any_surface(sp.position, walls, slack_m=0.01), (
                f"σ={sigma_m} m trial={trial} ch{sp.channel}: position "
                f"{sp.position} not on any perturbed wall"
            )

            drifts.append(_drift_m(sp_base, sp.position))

            # Wall-flip tally (perturbed walls are same ordering as baseline,
            # just slightly displaced — index is the structural identifier).
            trial_idx = _wall_index_for(sp.position, walls)
            if trial_idx != base_wall_idx[ch_i]:
                flips_per_channel[ch_i] += 1

    # --- Diagnostic (printed under -s; not asserted) --------------------- #
    arr = np.asarray(drifts, dtype=np.float64)
    flip_rates = [c / N_TRIALS for c in flips_per_channel]
    msg = (
        f"\n[CHARACTERISATION σ={sigma_m * 100:.0f} cm, n={arr.size}] "
        f"drift_mean={arr.mean():.4f} m  p50={np.median(arr):.4f} m  "
        f"p95={np.percentile(arr, 95):.4f} m  max={arr.max():.4f} m\n"
        f"[CHARACTERISATION σ={sigma_m * 100:.0f} cm] "
        f"wall_flip_rate per channel (n={N_TRIALS} trials): "
        f"{[f'{r:.2f}' for r in flip_rates]} "
        f"(0.00 = always same wall as baseline; 1.00 = always different)"
    )
    # Print directly so it surfaces under `pytest -s`. Also retained in
    # capsys so a failing test prints it on report.
    print(msg)
