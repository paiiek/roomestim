"""RoomCollection -> collection.yaml manifest writer (ADR 0049, Phase 1).

The manifest is a thin, additive bundle index: collection ``name`` + ``version``
+ an ordered ``rooms[]`` list of ``{name, room_ref, layout_ref}`` where the refs
are paths RELATIVE to the manifest's own directory (Risk #3 — no absolute paths
leak into goldens; the reader resolves them against the manifest parent).

There is intentionally NO geometry merge, NO combined volume / RT60, and NO
inter-room pose — a collection is N independent single-room artifacts (ADR 0049).
The single-room ``room_schema`` / ``room.yaml`` / ``layout.yaml`` writers are NOT
touched; this writer only emits the index.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from roomestim.collection import RoomCollection

_SCHEMA_VERSION = "0.1-draft"


def _proto_dir() -> Path:
    """Resolve the in-package ``roomestim/proto/`` directory (ADR 0007).

    ``__file__`` is at ``<...>/roomestim/export/collection_yaml.py`` so
    ``parents[1]`` is the ``roomestim/`` package root; the schema is bundled
    in-package (``proto/*.json`` package-data) so an installed wheel ships and
    resolves it.
    """
    return Path(__file__).resolve().parents[1] / "proto"


def _schema_path() -> Path:
    return _proto_dir() / "collection_schema.v0_1.draft.json"


def _load_schema() -> dict[str, Any]:
    with _schema_path().open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def collection_to_dict(
    collection: RoomCollection,
    *,
    room_refs: list[str],
    layout_refs: list[str | None],
    combined_ref: str | None = None,
) -> dict[str, Any]:
    """Return a YAML-serializable manifest dict for ``collection``.

    Parameters
    ----------
    collection:
        The :class:`RoomCollection` to index.
    room_refs:
        Parallel-indexed relative paths (to the manifest dir) of each room's
        ``room.yaml``. Length must equal ``len(collection.rooms)``.
    layout_refs:
        Parallel-indexed relative paths of each room's ``layout.yaml``, or
        ``None`` for a room with no placement. Length must equal
        ``len(collection.rooms)``.
    combined_ref:
        Optional relative path (to the manifest dir) of a combined glTF/GLB
        visual assembly. Emitted only when not ``None``.

    The entry ``name`` is taken from each ``RoomModel.name`` (the refs are the
    on-disk filenames the caller actually wrote). Refs MUST be relative to the
    manifest directory — absolute refs are rejected so no machine path leaks.
    A per-room ``offset`` (from ``collection.offsets``) is emitted only when it
    is non-``None`` — an all-``None`` offsets list yields a manifest
    byte-identical to the offset-free path.
    """
    n = len(collection.rooms)
    if len(room_refs) != n or len(layout_refs) != n:
        raise ValueError(
            "collection_to_dict: room_refs / layout_refs must be parallel-"
            f"indexed with rooms (got {len(room_refs)} room_refs, "
            f"{len(layout_refs)} layout_refs for {n} rooms)."
        )

    rooms_block: list[dict[str, Any]] = []
    for room, room_ref, layout_ref, offset in zip(
        collection.rooms, room_refs, layout_refs, collection.offsets
    ):
        if Path(room_ref).is_absolute():
            raise ValueError(
                f"collection manifest room_ref must be relative to the manifest "
                f"directory, got absolute path: {room_ref!r}"
            )
        if layout_ref is not None and Path(layout_ref).is_absolute():
            raise ValueError(
                f"collection manifest layout_ref must be relative to the manifest "
                f"directory, got absolute path: {layout_ref!r}"
            )
        entry: dict[str, Any] = {
            "name": room.name,
            "room_ref": room_ref,
            "layout_ref": layout_ref,
        }
        if offset is not None:
            entry["offset"] = [float(c) for c in offset]
        rooms_block.append(entry)

    manifest: dict[str, Any] = {
        "version": _SCHEMA_VERSION,
        "name": collection.name,
        "rooms": rooms_block,
    }
    if combined_ref is not None:
        if Path(combined_ref).is_absolute():
            raise ValueError(
                f"collection manifest combined_ref must be relative to the "
                f"manifest directory, got absolute path: {combined_ref!r}"
            )
        manifest["combined_ref"] = combined_ref
    return manifest


def write_collection_yaml(
    collection: RoomCollection,
    out_path: Path | str,
    *,
    room_refs: list[str],
    layout_refs: list[str | None],
    combined_ref: str | None = None,
) -> None:
    """Serialize ``collection`` to ``out_path`` as a validated manifest YAML.

    Order of operations (any failure aborts BEFORE any write):
      1. Build the manifest dict via :func:`collection_to_dict` (rejects
         absolute / mismatched refs).
      2. Validate against ``collection_schema.v0_1.draft.json`` (Draft 2020-12).
      3. Write via ``yaml.safe_dump(..., sort_keys=False)``.
    """
    data = collection_to_dict(
        collection,
        room_refs=room_refs,
        layout_refs=layout_refs,
        combined_ref=combined_ref,
    )
    Draft202012Validator(_load_schema()).validate(data)
    out_path = Path(out_path)
    with out_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


__all__ = ["collection_to_dict", "write_collection_yaml"]
