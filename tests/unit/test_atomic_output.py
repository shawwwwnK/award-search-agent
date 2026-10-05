"""Characterize both ranking writers before and after shared implementation."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from award_agent.cli import ranking_match, ranking_styles

Writer = Callable[[Path, str], None]


@pytest.fixture(
    params=[ranking_match._write_new_atomic, ranking_styles._write_new_atomic],
    ids=["matching", "styles"],
)
def writer(request: pytest.FixtureRequest) -> Writer:
    return cast(Writer, request.param)


@pytest.mark.parametrize("rendered", ["", "café", "already terminated\n"])
def test_writer_preserves_bytes_and_adds_one_newline(
    writer: Writer, tmp_path: Path, rendered: str,
) -> None:
    path = tmp_path / "nested" / "result.json"
    writer(path, rendered)
    assert path.read_bytes() == (rendered + "\n").encode("utf-8")
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("kind", ["file", "symlink", "dangling_symlink"])
def test_writer_does_not_replace_existing_paths(
    writer: Writer, tmp_path: Path, kind: str,
) -> None:
    path = tmp_path / "result.json"
    target = tmp_path / "target.json"
    if kind == "file":
        path.write_bytes(b"original evidence")
    else:
        if kind == "symlink":
            target.write_bytes(b"original evidence")
        path.symlink_to(target)
    before = set(tmp_path.iterdir())

    with pytest.raises(FileExistsError):
        writer(path, "replacement")

    assert set(tmp_path.iterdir()) == before
    if kind != "file":
        assert path.is_symlink() and path.readlink() == target
    if kind == "dangling_symlink":
        assert not target.exists()
    else:
        assert path.read_bytes() == b"original evidence"


def test_writer_preserves_destination_created_during_publication(
    writer: Writer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "result.json"
    real_link = os.link

    def competing_link(source: Path, destination: Path) -> None:
        assert source.parent == destination.parent
        assert source.name.startswith(f".{destination.name}.")
        assert source.name.endswith(".tmp")
        assert source.read_bytes() == b"new evidence\n"
        destination.write_bytes(b"competing evidence")
        real_link(source, destination)

    monkeypatch.setattr(os, "link", competing_link)
    with pytest.raises(FileExistsError):
        writer(path, "new evidence")
    assert path.read_bytes() == b"competing evidence"
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("operation", ["fsync", "link"])
def test_publication_failure_propagates_and_cleans_temporary_file(
    writer: Writer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str,
) -> None:
    path = tmp_path / "result.json"
    failure = OSError(f"injected {operation} failure")

    def fail(*_args: object, **_kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(os, operation, fail)
    with pytest.raises(OSError) as caught:
        writer(path, "new evidence")
    assert caught.value is failure
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("link_fails", [False, True])
def test_cleanup_error_propagates_even_after_publication(
    writer: Writer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link_fails: bool,
) -> None:
    path = tmp_path / "result.json"
    cleanup_failure = OSError("injected cleanup failure")

    def fail_unlink(_path: Path, missing_ok: bool = False) -> None:
        raise cleanup_failure

    def fail_link(*_args: object, **_kwargs: object) -> None:
        raise OSError("injected link failure")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_unlink)
        if link_fails:
            patch.setattr(os, "link", fail_link)
        with pytest.raises(OSError) as caught:
            writer(path, "new evidence")
        assert caught.value is cleanup_failure

    assert path.exists() is not link_fails
    if not link_fails:
        assert path.read_bytes() == b"new evidence\n"
    leftovers = list(tmp_path.glob(".result.json.*.tmp"))
    assert len(leftovers) == 1
    leftovers[0].unlink()


@pytest.mark.parametrize("stage", ["matching", "styles"])
def test_cli_rejects_dangling_symlink_before_loading_inputs(
    tmp_path: Path, stage: str,
) -> None:
    output = tmp_path / "result.json"
    target = tmp_path / "absent.json"
    output.symlink_to(target)
    if stage == "matching":
        main = ranking_match.main
        arguments = ["--bundle", "absent-bundle", "--result", "absent-result"]
    else:
        main = ranking_styles.main
        arguments = ["--matched", "absent-matched", "--fx-snapshot", "absent-fx"]
    with pytest.raises(SystemExit) as caught:
        main([*arguments, "--output", str(output)])
    assert caught.value.code == 2
    assert output.is_symlink() and not target.exists()
