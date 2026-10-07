from toolong.help import HELP_MD


def test_help_lists_g_for_the_start_and_capital_g_for_the_end():
    assert "- `home` or `g` / `end` or `G` Jump to start or end of file." in HELP_MD


def test_help_lists_y_for_copying_the_pointer_line():
    assert "- `y` Copy (yank) current line in pointer mode.\n" in HELP_MD
    pointer_mode = HELP_MD.split("### Pointer mode", 1)[1]
    assert "Press `y` to copy" in pointer_mode
    assert "OSC 52" in pointer_mode
