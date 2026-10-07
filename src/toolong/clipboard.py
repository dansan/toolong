from __future__ import annotations

import os
import subprocess
from typing import Mapping

WAYLAND_COMMANDS = [["wl-copy"]]
X11_COMMANDS = [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]


def copy_with_local_tools(text: str, environ: Mapping[str, str] = os.environ) -> bool:
    """Copy text with wl-copy, and with xclip or else xsel, where installed and their display is set.

    Returns:
        True if a tool copied the text.
    """
    copied = False
    if environ.get("WAYLAND_DISPLAY"):
        copied |= run_first_installed(WAYLAND_COMMANDS, text)
    if environ.get("DISPLAY"):
        copied |= run_first_installed(X11_COMMANDS, text)
    return copied


def run_first_installed(commands: list[list[str]], text: str) -> bool:
    for command in commands:
        try:
            # The tools leave a process behind that serves the clipboard; capturing its
            # output would wait for that process to exit.
            completed = subprocess.run(
                command,
                input=text.encode(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except FileNotFoundError:
            continue
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0
    return False
