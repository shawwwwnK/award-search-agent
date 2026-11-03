"""Atomic V17 editorial block splices over an already decoded complete draft."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, cast

from .focused_comparison_wire import schema as document_schema
from .focused_patch_contracts import FocusedPatch
from .interactive_contracts import InteractivePreparedInput


def patch_schema(prepared: InteractivePreparedInput) -> dict[str, object]:
    block_item = cast(dict[str, Any], document_schema(prepared)["properties"])["blocks"]["items"]
    blocks: dict[str, object] = {"type": "array", "items": deepcopy(block_item)}
    if prepared.packet.get("composition_format") in {"complete-v16", "complete-v17", "complete-v18", "complete-v19"}:
        blocks["maxItems"] = 1
    return {"type": "object", "additionalProperties": False,
            "properties": {"edits": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {"start": {"type": "integer"}, "end": {"type": "integer"},
                               "blocks": blocks},
                "required": ["start", "end", "blocks"]}}}, "required": ["edits"]}


def decode_patch(raw: str | dict[str, Any], *, atomic: bool = False) -> FocusedPatch:
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict) or set(value) != {"edits"} or not isinstance(value["edits"], list):
        raise ValueError("editorial patch requires exactly an edits array")
    for index, edit in enumerate(value["edits"]):
        if (not isinstance(edit, dict) or set(edit) != {"start", "end", "blocks"} or
                type(edit["start"]) is not int or type(edit["end"]) is not int or
                not isinstance(edit["blocks"], list) or
                any(not isinstance(block, dict) for block in edit["blocks"])):
            raise ValueError(f"editorial edit {index} has invalid fields")
        if atomic and (edit["end"] != edit["start"] + 1 or len(edit["blocks"]) > 1):
            raise ValueError("atomic editorial edits replace or delete exactly one original block")
    return FocusedPatch.model_validate(value)


def apply_patch(draft_wire: str, patch: FocusedPatch, *, atomic: bool = False) -> str:
    """Apply sorted, unique, nonoverlapping edits without changing untouched blocks."""
    draft = json.loads(draft_wire)
    if not isinstance(draft, dict) or set(draft) != {"blocks"} or not isinstance(draft["blocks"], list):
        raise ValueError("editorial draft is not a complete blocks document")
    original = draft["blocks"]
    length = len(original)
    cursor = 0
    previous_start = -1
    output: list[dict[str, Any]] = []
    for edit in patch.edits:
        if atomic and (edit.end != edit.start + 1 or len(edit.blocks) > 1):
            raise ValueError("atomic editorial edits replace or delete exactly one original block")
        if (edit.start <= previous_start or edit.start < cursor or
                edit.start > edit.end or edit.end > length):
            raise ValueError("editorial edits must be sorted, unique, disjoint and within draft bounds")
        output.extend(deepcopy(original[cursor:edit.start]))
        output.extend(deepcopy(edit.blocks))
        cursor = edit.end
        previous_start = edit.start
    output.extend(deepcopy(original[cursor:]))
    return json.dumps({"blocks": output}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
