"""tests/test_cli_image_backend.py — Phase 4 image-backend CLI wiring.

Covers the opt-in EXPERIMENTAL `--backend image` tier (ADR 0045 §image backend):

  * Hard `--experimental` gate: `--backend image` without `--experimental` exits
    1 with the gate error and imports NO torch (the gate is pure argparse-level,
    fires before the adapter is constructed).
  * Provenance-aware "ESTIMATED" disclosure: a successful image ingest/run that
    produced a `provenance="reconstructed"` RoomModel prints the ESTIMATED notice.
  * ZInD ToU surfacing: `--weights zind --experimental` without
    `--accept-zind-tou` surfaces the non-commercial Terms-of-Use error.
  * Measured backends (roomplan/polycam) are unchanged — no ESTIMATED notice.
  * `import roomestim.cli` stays torch-free (subprocess sys.modules check).

All tests run WITHOUT torch: the image adapter's `parse` (the only torch path)
is monkeypatched to a canned reconstructed RoomModel, so nothing here downloads
weights or imports torch.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from roomestim.cli import main
from roomestim.model import RoomModel

from tests.fixtures.synthetic_rooms import shoebox

_FIXTURE_JSON = Path(__file__).parent / "fixtures" / "lab_room.json"


def _reconstructed_room() -> RoomModel:
    """A synthetic RoomModel tagged provenance='reconstructed' (image-derived)."""
    base = shoebox(name="img_recon")
    return RoomModel(
        name=base.name,
        floor_polygon=base.floor_polygon,
        ceiling_height_m=base.ceiling_height_m,
        surfaces=base.surfaces,
        listener_area=base.listener_area,
        objects=[],
        provenance="reconstructed",
    )


def _stub_parse_reconstructed(self, path, *, scale_anchor=None, octave_band=False):  # noqa: ANN001, ARG001
    return _reconstructed_room()


# --------------------------------------------------------------------------- #
# Hard experimental gate (torch-free: must fail before adapter construction)
# --------------------------------------------------------------------------- #


def test_ingest_image_without_experimental_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(
        ["ingest", "--backend", "image", "--input", str(tmp_path / "pano.png"),
         "--out-dir", str(tmp_path)]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("error:")
    assert "experimental" in captured.err
    assert "--experimental" in captured.err
    # The gate must fire before any adapter/torch import on this process.
    assert "torch" not in sys.modules
    assert not (tmp_path / "room.yaml").exists()


def test_run_image_without_experimental_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(
        ["run", "--backend", "image", "--input", str(tmp_path / "pano.png"),
         "--algorithm", "vbap", "--n-speakers", "6", "--out-dir", str(tmp_path)]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("error:")
    assert "experimental" in captured.err
    assert "torch" not in sys.modules


# --------------------------------------------------------------------------- #
# ESTIMATED disclosure for reconstructed rooms (ingest + run)
# --------------------------------------------------------------------------- #


def test_ingest_image_experimental_writes_room_and_prints_estimated(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from roomestim.adapters.image import ImageAdapter

    monkeypatch.setattr(ImageAdapter, "parse", _stub_parse_reconstructed)

    rc = main(
        ["ingest", "--backend", "image", "--experimental", "--cam-height", "1.6",
         "--input", str(tmp_path / "pano.png"), "--out-dir", str(tmp_path)]
    )
    assert rc == 0
    assert (tmp_path / "room.yaml").exists()
    captured = capsys.readouterr()
    assert "ESTIMATED" in captured.err
    assert "provenance=reconstructed" in captured.err
    assert "NOT install-grade" in captured.err


def test_run_image_experimental_writes_outputs_and_prints_estimated(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from roomestim.adapters.image import ImageAdapter

    monkeypatch.setattr(ImageAdapter, "parse", _stub_parse_reconstructed)

    rc = main(
        ["run", "--backend", "image", "--experimental", "--cam-height", "1.6",
         "--input", str(tmp_path / "pano.png"), "--algorithm", "vbap",
         "--n-speakers", "6", "--out-dir", str(tmp_path)]
    )
    assert rc == 0
    assert (tmp_path / "room.yaml").exists()
    assert (tmp_path / "layout.yaml").exists()
    captured = capsys.readouterr()
    assert "ESTIMATED" in captured.err


def test_image_adapter_built_with_cli_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--cam-height → ScaleAnchor; --weights/--accept-zind-tou → constructor."""
    captured_kwargs: dict[str, object] = {}
    captured_anchor: dict[str, object] = {}

    import roomestim.adapters.image as image_mod

    orig_init = image_mod.ImageAdapter.__init__

    def spy_init(self, **kwargs):  # noqa: ANN001, ANN003
        captured_kwargs.update(kwargs)
        orig_init(self, **kwargs)

    def spy_parse(self, path, *, scale_anchor=None, octave_band=False):  # noqa: ANN001, ARG001
        captured_anchor["anchor"] = scale_anchor
        return _reconstructed_room()

    monkeypatch.setattr(image_mod.ImageAdapter, "__init__", spy_init)
    monkeypatch.setattr(image_mod.ImageAdapter, "parse", spy_parse)

    rc = main(
        ["ingest", "--backend", "image", "--experimental", "--cam-height", "1.55",
         "--weights", "st3d", "--input", str(tmp_path / "p.png"),
         "--out-dir", str(tmp_path)]
    )
    assert rc == 0
    assert captured_kwargs["weights"] == "st3d"
    assert captured_kwargs["accept_noncommercial"] is False
    anchor = captured_anchor["anchor"]
    assert anchor is not None
    assert anchor.type == "known_distance"
    assert anchor.length_m == pytest.approx(1.55)


def test_image_no_cam_height_passes_none_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Omitting --cam-height passes scale_anchor=None so the adapter warns+defaults."""
    seen: dict[str, object] = {}

    import roomestim.adapters.image as image_mod

    def spy_parse(self, path, *, scale_anchor=None, octave_band=False):  # noqa: ANN001, ARG001
        seen["anchor"] = scale_anchor
        return _reconstructed_room()

    monkeypatch.setattr(image_mod.ImageAdapter, "parse", spy_parse)

    rc = main(
        ["ingest", "--backend", "image", "--experimental",
         "--input", str(tmp_path / "p.png"), "--out-dir", str(tmp_path)]
    )
    assert rc == 0
    assert seen["anchor"] is None


# --------------------------------------------------------------------------- #
# ZInD ToU surfacing (torch-free: parse raises the same ValueError the real
# checkpoint resolver raises when the non-commercial ToU is not accepted)
# --------------------------------------------------------------------------- #


def test_image_zind_without_tou_surfaces_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import roomestim.adapters.image as image_mod
    from roomestim.vision.checkpoints import resolve_checkpoint

    def parse_resolving_ckpt(self, path, *, scale_anchor=None, octave_band=False):  # noqa: ANN001, ARG001
        # Mirrors the real torch path: resolving the zind checkpoint without
        # ToU acceptance raises ValueError (no download, no torch).
        resolve_checkpoint(self._weights, accept_noncommercial=self._accept_noncommercial)
        return _reconstructed_room()  # pragma: no cover - never reached

    monkeypatch.setattr(image_mod.ImageAdapter, "parse", parse_resolving_ckpt)

    rc = main(
        ["ingest", "--backend", "image", "--experimental", "--weights", "zind",
         "--input", str(tmp_path / "p.png"), "--out-dir", str(tmp_path)]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("error:")
    assert "ZInD" in captured.err or "zind" in captured.err.lower()
    assert "torch" not in sys.modules


def test_image_zind_resolver_raises_value_error_without_tou() -> None:
    """Direct contract: the resolver raises ValueError (CLI catches → exit 1)."""
    from roomestim.vision.checkpoints import resolve_checkpoint

    import os

    saved = os.environ.pop("ROOMESTIM_HORIZONNET_CKPT", None)
    os.environ.pop("ROOMESTIM_ACCEPT_ZIND_TOU", None)
    try:
        with pytest.raises(ValueError):
            resolve_checkpoint("zind", accept_noncommercial=False)
    finally:
        if saved is not None:
            os.environ["ROOMESTIM_HORIZONNET_CKPT"] = saved


# --------------------------------------------------------------------------- #
# Measured backends unchanged — no ESTIMATED notice
# --------------------------------------------------------------------------- #


def test_roomplan_ingest_no_estimated_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(
        ["ingest", "--backend", "roomplan", "--input", str(_FIXTURE_JSON),
         "--out-dir", str(tmp_path)]
    )
    assert rc == 0
    assert (tmp_path / "room.yaml").exists()
    captured = capsys.readouterr()
    assert "ESTIMATED" not in captured.err
    assert "ESTIMATED" not in captured.out


def test_roomplan_run_no_estimated_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(
        ["run", "--backend", "roomplan", "--input", str(_FIXTURE_JSON),
         "--algorithm", "vbap", "--n-speakers", "8", "--out-dir", str(tmp_path)]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "ESTIMATED" not in captured.err
    assert "ESTIMATED" not in captured.out


# --------------------------------------------------------------------------- #
# Help / usage describes the experimental image backend
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("command", ["ingest", "run"])
def test_help_shows_image_backend_args(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main([command, "--help"])
    out = capsys.readouterr().out
    assert "image" in out
    assert "--cam-height" in out
    assert "--experimental" in out
    assert "--accept-zind-tou" in out
    assert "EXPERIMENTAL" in out or "experimental" in out


# --------------------------------------------------------------------------- #
# import roomestim.cli stays torch-free
# --------------------------------------------------------------------------- #


def test_import_cli_is_torch_free() -> None:
    code = (
        "import sys; import roomestim.cli; "
        "assert 'torch' not in sys.modules, sorted(m for m in sys.modules if 'torch' in m); "
        "print('OK')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


# --------------------------------------------------------------------------- #
# v0.28.0 — low-ceiling under-report stderr notice
# --------------------------------------------------------------------------- #


def test_low_ceiling_notice_fires_on_low_confidence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The stderr NOTE fires only for ceiling_confidence='low' and labels HEURISTIC."""
    from roomestim.cli import _maybe_print_low_ceiling_notice

    room = shoebox(name="low_ceiling")
    room.ceiling_coverage = 0.18
    room.ceiling_confidence = "low"
    _maybe_print_low_ceiling_notice(room)
    captured = capsys.readouterr()
    assert "UNDER-reported" in captured.err
    assert "18%" in captured.err
    assert "HEURISTIC not calibrated" in captured.err
    assert captured.out == ""


def test_low_ceiling_notice_silent_on_high_and_unknown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No notice for high-confidence or unknown (non-measured) rooms."""
    from roomestim.cli import _maybe_print_low_ceiling_notice

    high = shoebox(name="high_ceiling")
    high.ceiling_coverage = 0.95
    high.ceiling_confidence = "high"
    _maybe_print_low_ceiling_notice(high)
    assert capsys.readouterr().err == ""

    unknown = shoebox(name="unknown_ceiling")  # default unknown / None
    _maybe_print_low_ceiling_notice(unknown)
    assert capsys.readouterr().err == ""
