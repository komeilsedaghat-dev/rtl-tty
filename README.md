# rtl-tty

Fix Persian / Arabic / Hebrew text in terminal AI tools (Claude Code and friends).

Mixed right-to-left and English text in a terminal often comes out scrambled: words swap places,
English terms jump to the wrong side of the sentence. `rtl-tty` runs your command inside a
pseudo-terminal and tells the terminal which rows are right-to-left, so they are laid out
right-to-left with English words staying where they belong.

```bash
rtl-tty claude
```

<!-- TODO: before/after GIF -->

## Install

```bash
pipx install rtl-tty        # once published to PyPI
# or from a checkout:
pipx install .
```

Requires Python 3.8+ on Linux. No dependencies. Optional alias:

```bash
alias claude='rtl-tty claude'
```

## Compatibility

| Terminal / tool | Status |
|---|---|
| GNOME Terminal 3.52 (VTE 0.76), Claude Code 2.1 | works (tested) |
| Other VTE terminals (Tilix, Terminator, ...) | expected to work, untested |
| tmux / screen | untested; likely to swallow the escape sequence |
| Kitty, Alacritty, WezTerm, iTerm2, Windows Terminal, VS Code terminal | not supported (no bidi layout at all in most of them) |
| Gemini CLI, Codex CLI, aider, opencode | untested |

Reports welcome: run `experiments/scp_demo.sh` in your terminal and open an issue with the result.

## How it works

Findings on GNOME Terminal / VTE 0.76, all reproducible with `experiments/scp_demo.sh`:

1. VTE lays rows out **left-to-right by default** and **discards** Unicode bidi control characters
   (RLI, PDI, RLM, ...), so the usual "wrap it in isolates" trick does nothing (demo case 5).
2. VTE has its own escape for this, **SCP** (`CSI 2 SPACE k` = this row is right-to-left). It works on
   a fresh row even with the cursor indented (demo cases 2 and 4), and the setting **persists on the
   following rows** until reset with `CSI 0 SPACE k`.
3. On a row that **already has text**, SCP only takes effect when sent in **column 0** (demo cases 6 and 7:
   the same rewrite is scrambled with SCP in column 1 and right-to-left with SCP in column 0).
   Claude Code redraws existing rows every frame and indents them, so a plain SCP has no effect there.

`rtl-tty` therefore buffers each output row until the cursor leaves it, decides once whether the
row contains RTL letters, and inserts `ESC 7`, `CR`, SCP, `ESC 8` (save cursor, go to column 0,
set direction, restore cursor) before the row's first text. Nothing else in the stream is changed.

## Options

```
rtl-tty [--mode scp|off] [--log FILE] COMMAND [ARGS...]
```

`--mode off` passes output through unchanged (handy for before/after comparisons).
`--log FILE` (or `RTL_TTY_LOG`) records raw and transformed output for debugging. **The log
contains everything shown on screen.**

## Limitations

- Direction is decided per row; a very long paragraph that the app wraps itself is handled row by row.
- Only rows containing RTL letters change; box-drawing and English rows are left alone.
- Window resizing and scrollback were not tested thoroughly.

## Development

```bash
python3 -m pytest
```

## License

MIT

---

## فارسی

`rtl-tty` متن فارسی (و عربی و عبری) را در ابزارهای هوش مصنوعی داخل ترمینال درست نمایش می‌دهد؛
مثلاً وقتی با Claude Code فارسی و انگلیسی را قاطی می‌نویسید و کلمه‌ها جابه‌جا می‌شوند.

```bash
rtl-tty claude
```

روش کار: ترمینال VTE (مثل GNOME Terminal) دستور مخصوص خودش را برای «این سطر راست‌به‌چپ است» دارد
(SCP) و کاراکترهای نامرئی جهت‌دهنده Unicode را نادیده می‌گیرد. این برنامه قبل از هر سطر فارسی همان دستور را
می‌فرستد. فعلاً فقط روی GNOME Terminal با Claude Code تست شده است.
