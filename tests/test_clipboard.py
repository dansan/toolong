from __future__ import annotations

from pathlib import Path

import pytest

from toolong.clipboard import copy_with_local_tools

DISPLAYS = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}


class FakeTools:
    """Clipboard tools on an otherwise empty PATH; each writes its input to <name>.out."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def install(self, name: str, exit_code: int = 0) -> None:
        tool = self.directory / name
        tool.write_text(f'#!/bin/sh\n/bin/cat > "{self.directory}/{name}.out"\nexit {exit_code}\n')
        tool.chmod(0o755)

    def copied(self, name: str) -> str | None:
        output = self.directory / f"{name}.out"
        return output.read_text(encoding="utf-8") if output.exists() else None


@pytest.fixture
def tools(tmp_path, monkeypatch) -> FakeTools:
    monkeypatch.setenv("PATH", str(tmp_path))
    return FakeTools(tmp_path)


def test_wayland_copies_with_wl_copy(tools):
    tools.install("wl-copy")
    tools.install("xclip")
    assert copy_with_local_tools("line ü", {"WAYLAND_DISPLAY": "wayland-0"})
    assert tools.copied("wl-copy") == "line ü"
    assert tools.copied("xclip") is None


def test_x11_copies_with_xclip_and_not_xsel(tools):
    tools.install("xclip")
    tools.install("xsel")
    assert copy_with_local_tools("line", {"DISPLAY": ":0"})
    assert tools.copied("xclip") == "line"
    assert tools.copied("xsel") is None


def test_x11_falls_back_to_xsel_without_xclip(tools):
    tools.install("xsel")
    assert copy_with_local_tools("line", {"DISPLAY": ":0"})
    assert tools.copied("xsel") == "line"


def test_wayland_with_xwayland_copies_with_both(tools):
    tools.install("wl-copy")
    tools.install("xclip")
    assert copy_with_local_tools("line", DISPLAYS)
    assert tools.copied("wl-copy") == tools.copied("xclip") == "line"


def test_no_tools_installed_is_not_an_error(tools):
    assert not copy_with_local_tools("line", DISPLAYS)


def test_no_display_runs_no_tool(tools):
    tools.install("wl-copy")
    tools.install("xclip")
    assert not copy_with_local_tools("line", {})
    assert tools.copied("wl-copy") is None
    assert tools.copied("xclip") is None


def test_failing_tool_is_reported(tools):
    tools.install("wl-copy", exit_code=1)
    assert not copy_with_local_tools("line", {"WAYLAND_DISPLAY": "wayland-0"})
