"""Test fixture package.

To enable A10 (`tests/test_acceptance_lab_room.py`):
    1. Drop ``lab_real.usdz`` from the iPad RoomPlan/Polycam scan into this directory.
    2. Rename ``lab_real_groundtruth.yaml.template`` → ``lab_real_groundtruth.yaml``
       and replace every ``TODO`` with the tape-measured value.
    3. Run ``pytest -m lab``.

See ``decisions.md`` D8/D9 for the human-gated handoff and ``.template`` for
the GT YAML schema.
"""
