"""Vendored HorizonNet inference code (MIT, (c) 2019 Cheng Sun).

Kept intentionally minimal and torch-free at import time. Do NOT import the
torch-backed model here: ``import roomestim.vision.horizonnet`` must stay
torch-free. Callers load the model inside guarded code via::

    from roomestim.vision.horizonnet.model import HorizonNet
    from roomestim.vision.horizonnet.misc.utils import load_trained_model

See ./LICENSE and ./NOTICE for license and weight-provenance details.
"""

from __future__ import annotations
