from toolong.help import HELP_MD


def test_help_lists_g_for_the_start_and_capital_g_for_the_end():
    assert "- `home` or `g` / `end` or `G` Jump to start or end of file." in HELP_MD


def test_help_lists_y_for_copying_the_pointer_line():
    assert "- `y` Copy (yank) current line in pointer mode. See section 'Copying' below" in HELP_MD
    pointer_mode = HELP_MD.split("### Pointer mode", 1)[1].split("###", 1)[0]
    assert "Press `y` to copy" in pointer_mode


def test_help_explains_the_clipboard_tools_and_their_packages():
    copying = HELP_MD.split("### Copying", 1)[1].split("###", 1)[0]
    assert "OSC 52" in copying
    assert "GNOME Terminal" in copying
    for name in ("`wl-copy`", "`wl-clipboard`", "`xclip`", "`xsel`"):
        assert name in copying
