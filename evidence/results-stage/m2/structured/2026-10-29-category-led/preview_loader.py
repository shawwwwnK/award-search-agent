"""Render a saved run with the preview source archived by that run."""

from __future__ import annotations

import hashlib
import types
import zipfile
from pathlib import Path
from typing import Any

import ledger
import run


def render_saved(directory: Path, artifact: Any) -> tuple[str, str]:
    member = str((run.HERE / "preview.py").relative_to(run.REPO))
    snapshot = ledger.read_json(directory / "source-snapshot.json")
    with zipfile.ZipFile(directory / "source-snapshot.zip") as archive:
        source = archive.read(member)
    if hashlib.sha256(source).hexdigest() != snapshot[member]:
        raise ValueError("archived preview differs from frozen source hash")
    module = types.ModuleType("archived_results_category_preview")
    module.__file__ = member
    # The archived module is repository-owned, hash checked, and imports stdlib only.
    exec(compile(source, member, "exec"), module.__dict__)  # noqa: S102
    return module.render_markdown(artifact), module.render_html(artifact)
