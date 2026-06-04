"""roomestim vision subpackage (optional ``[vision]`` extra).

This package wraps optional, torch-backed image->geometry inference (HorizonNet
panorama layout estimation). It is intentionally torch-free at import time:
``import roomestim.vision`` must NOT pull in torch/torchvision so that the core
package boundary (ADR 0045 gate #4) stays clean and the canonical gate stays
green even when torchvision is broken/absent.

Heavy, torch-backed code lives under ``roomestim.vision.horizonnet`` and must
only be imported inside guarded code paths, e.g.::

    from roomestim.vision.horizonnet.model import HorizonNet  # needs [vision]

Checkpoint *path resolution* (``roomestim.vision.checkpoints``) is torch-free
and safe to import unconditionally.
"""

from __future__ import annotations
