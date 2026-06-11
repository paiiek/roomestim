"""Resolve HorizonNet checkpoint paths, downloading on first use.

This module NEVER bundles model weights. It only resolves a filesystem path to
a checkpoint, downloading it on first use into a per-user cache. It is
deliberately torch-free (it only deals with file paths), so importing it does
not pull in torch/torchvision and stays inside the core/web boundary
(ADR 0045 gate #4). The optional ``huggingface_hub`` / ``gdown`` dependencies
(declared in the ``[vision]`` extra) are imported lazily inside the functions,
so a plain ``import roomestim.vision.checkpoints`` works even when those extras
are absent.

Code vs weights licensing
-------------------------
The vendored HorizonNet *code* is MIT (see
``roomestim/vision/horizonnet/LICENSE``). The *weights* are not MIT and carry
their own dataset-derived terms:

* ``st3d`` — trained on the Structured3D research dataset; the default,
  comparatively permissive ("GREEN-ish") option for research use.
* ``zind`` — trained on the Zillow Indoor Dataset (ZInD), whose Terms of Use
  are academic / NON-COMMERCIAL and require explicit acceptance before use.

Environment variables
---------------------
* ``ROOMESTIM_HORIZONNET_CKPT`` — absolute path to a local checkpoint. If set,
  it is returned directly (no download); lets dev/tests reuse a local file.
* ``ROOMESTIM_CACHE_DIR`` — override the cache root (default
  ``~/.cache/roomestim``).
* ``ROOMESTIM_ACCEPT_ZIND_TOU=1`` — accept the ZInD non-commercial Terms of Use
  (equivalent to passing ``accept_noncommercial=True``).
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

__all__ = ["resolve_checkpoint"]

# Hugging Face Hub mirror for the Structured3D-trained resnet50+rnn weights.
_HF_ST3D_REPO = "gum-tech/horizonnet-resnet50-rnn"
# Expected filename inside the HF repo. Override via ROOMESTIM_HORIZONNET_HF_FILE
# if the mirror layout differs.
_HF_ST3D_FILENAME = "resnet50_rnn__st3d.pth"

# Google Drive file id for the ZInD-trained weights (non-commercial ToU).
_GDRIVE_ZIND_ID = "1FrMdk7Z4_sTZOOW65Ek77WbjiDbV98uJ"
_ZIND_FILENAME = "resnet50_rnn__zind.pth"

_ZIND_TOU_MESSAGE = (
    "The 'zind' HorizonNet weights are trained on the Zillow Indoor Dataset "
    "(ZInD), whose Terms of Use are academic / NON-COMMERCIAL and require "
    "explicit acceptance. To proceed, pass accept_noncommercial=True or set "
    "the environment variable ROOMESTIM_ACCEPT_ZIND_TOU=1. By accepting you "
    "confirm your use complies with the ZInD ToU "
    "(https://github.com/zillow/zind#license). The default 'st3d' weights "
    "are trained on the Structured3D research dataset and carry their own "
    "dataset-derived terms; verify suitability for your use yourself."
)


def _cache_dir() -> Path:
    """Return the roomestim HorizonNet cache directory (created on demand)."""
    override = os.environ.get("ROOMESTIM_CACHE_DIR")
    if override:
        root = Path(override)
    else:
        try:
            import platformdirs

            root = Path(platformdirs.user_cache_dir("roomestim"))
        except Exception:
            root = Path.home() / ".cache" / "roomestim"
    cache = root / "horizonnet"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _resolve_st3d() -> Path:
    """Download (cached) and return the Structured3D-trained checkpoint."""
    filename = os.environ.get("ROOMESTIM_HORIZONNET_HF_FILE", _HF_ST3D_FILENAME)
    repo_id = os.environ.get("ROOMESTIM_HORIZONNET_HF_REPO", _HF_ST3D_REPO)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:  # pragma: no cover - exercised out-of-gate
        raise ImportError(
            "Resolving the 'st3d' checkpoint requires huggingface_hub. Install "
            "the vision extra: pip install 'roomestim[vision]'."
        ) from exc
    path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        cache_dir=str(_cache_dir()),
    )
    return Path(path)


def _resolve_zind() -> Path:
    """Download (cached) and return the ZInD-trained checkpoint.

    Caller must have already confirmed acceptance of the ZInD ToU.
    """
    dest = _cache_dir() / _ZIND_FILENAME
    if dest.exists():
        return dest
    try:
        import gdown
    except ImportError as exc:  # pragma: no cover - exercised out-of-gate
        raise ImportError(
            "Resolving the 'zind' checkpoint requires gdown. Install the vision "
            "extra: pip install 'roomestim[vision]'."
        ) from exc
    # ToU notice surfaced on use, per the academic/non-commercial terms. Routed
    # through warnings (not print) so library callers' stdout stays clean.
    warnings.warn(_ZIND_TOU_MESSAGE, stacklevel=2)
    # gdown ships no type stubs; download() is a public runtime attribute.
    gdown.download(id=_GDRIVE_ZIND_ID, output=str(dest), quiet=False)  # type: ignore[attr-defined]
    return dest


def resolve_checkpoint(
    name: str = "st3d", *, accept_noncommercial: bool = False
) -> Path:
    """Resolve a HorizonNet checkpoint path, downloading on first use.

    Parameters
    ----------
    name:
        Which weights to resolve. ``"st3d"`` (default) is the Structured3D
        research checkpoint; ``"zind"`` is the ZInD non-commercial checkpoint.
    accept_noncommercial:
        Required (or env ``ROOMESTIM_ACCEPT_ZIND_TOU=1``) to resolve
        ``name="zind"``; acknowledges the ZInD academic / non-commercial ToU.

    Returns
    -------
    Path
        Filesystem path to the resolved checkpoint.

    Notes
    -----
    The ``ROOMESTIM_HORIZONNET_CKPT`` environment variable, when set, takes
    precedence over everything and is returned directly (no download), letting
    dev/tests reuse a local file.
    """
    local_override = os.environ.get("ROOMESTIM_HORIZONNET_CKPT")
    if local_override:
        return Path(local_override)

    if name == "st3d":
        return _resolve_st3d()

    if name == "zind":
        accepted = accept_noncommercial or os.environ.get(
            "ROOMESTIM_ACCEPT_ZIND_TOU"
        ) == "1"
        if not accepted:
            raise ValueError(_ZIND_TOU_MESSAGE)
        return _resolve_zind()

    raise ValueError(
        f"Unknown checkpoint name {name!r}; expected 'st3d' or 'zind'."
    )
