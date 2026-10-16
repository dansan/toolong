# Changelog

## 1.6.0 (2026-10-16)

### Added

- Read log lines in the ADR 0010 format:
  color them by level,
  read their timestamps,
  and decode the logfmt data after the `|`.
- Show the fields of an ADR 0010 line as a table in the line panel.
- Find ADR 0010 lines by field with `key=value` and `key!=value` queries,
  with autocompletion of field names and values.
  Check *Fields* in the find dialog, or press `ctrl+e`, to switch to field queries.
- Show only the lines in a time range with `--since` and `--until`,
  also when merging files and reading piped input.
- Read timestamps without a UTC offset, such as those of deprecated univention-debug lines,
  in the time zone set with `--timezone`, `Europe/Berlin` by default.
- Color univention-debug levels and deprecated univention-debug lines.
- Copy the pointer line to the clipboard with `y`
  ([Textualize/toolong#62](https://github.com/Textualize/toolong/pull/62)
  by Anders Norman).
  Besides OSC 52, copy with `wl-copy`, `xclip` or `xsel` if one of them is installed.
- Copy the pointer line as a Python dict with `P` and as JSON with `J`.
  Data values that are decimal numbers are copied as ints and floats,
  and `true` and `false` as booleans.
- Show LDAP DNs decoded as in RFC 4514 in the line panel,
  also inside Python lists and dicts.
- Debian package for Debian Bookworm,
  which bundles the textual and rich versions from `poetry.lock`.
- GitLab CI builds and tests the Debian package and the wheel,
  and publishes both in a GitLab release for each version tag.
  The wheel is also uploaded to the project's PyPI registry.

### Changed

- `g` jumps to the start and `G` to the end of the file, as in vim and less
  ([Textualize/toolong#51](https://github.com/Textualize/toolong/pull/51)
  by Luka Markušić).
- Poll watched files every 0.25 s instead of every 0.05 s,
  which lowers the CPU load while tailing on Linux
  ([trissim/toolong@fe2dfd4](https://github.com/trissim/toolong/commit/fe2dfd46df3f7f17049e3a39c491108e25b8277a)
  by Tristan Simas).

### Fixed

- High CPU load while reading piped input
  ([Textualize/toolong#70](https://github.com/Textualize/toolong/pull/70)
  by Matt McKay).
  Polling of stdin now stops when the input ends
  ([tomdeblauwe/toolong#1](https://github.com/tomdeblauwe/toolong/pull/1)
  by Arne Depuydt).
- Long lines with many spaces no longer hang the log format detection
  ([Textualize/toolong#56](https://github.com/Textualize/toolong/pull/56)
  by Dylan LEROUX).
- Tailing scrolls to the real end of the file,
  including the lines that arrived while tailing was off
  ([Textualize/toolong#77](https://github.com/Textualize/toolong/pull/77)
  by tomdeblauwe).

## 1.5.0 (2024-04-28)

Forked from [Textualize/toolong](https://github.com/Textualize/toolong)
at commit [5aa22ee](https://github.com/Textualize/toolong/commit/5aa22ee878026f46d4d265905c4e1df4d37842ae),
the newest upstream version.
See the upstream repository for the changes up to this version.
