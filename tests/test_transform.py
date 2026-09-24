import re
from rtl_tty.transform import Transformer, SCP_RTL, SCP_DEFAULT, is_rtl


def run(b, mode="scp"):
    t = Transformer(mode)
    return t.feed(b) + t.flush()


def test_persian_row_marked_before_first_text():
    assert run("hello سلام\n".encode()) == f"{SCP_RTL}hello سلام\n"


def test_prompt_glyph_before_persian_still_gets_marker_first():
    assert run("\x1b[2m❯ \x1b[0mسلام\n".encode()) == f"\x1b[2m{SCP_RTL}❯ \x1b[0mسلام\n"


def test_english_row_gets_default():
    assert run(b"plain\n") == f"{SCP_DEFAULT}plain\n"


def test_blank_and_escape_only_rows_untouched():
    assert run(b"\n\x1b[2K\n") == "\n\x1b[2K\n"


def test_word_by_word_row_is_one_decision():
    # Claude Code positions each word with CSI n G; these are not row boundaries.
    out = run("\x1b[3Gcup\x1b[9Gسلام\x1b[13Gof\n".encode())
    assert out == f"\x1b[3G{SCP_RTL}cup\x1b[9Gسلام\x1b[13Gof\n"


def test_indented_row_marker_comes_after_indent_move_but_restores_cursor():
    # the marker itself jumps to column 0 then restores (ESC 7 / ESC 8)
    out = run("\x1b[2Cسلام\n".encode())
    assert out == f"\x1b[2C{SCP_RTL}سلام\n"
    assert SCP_RTL.startswith("\x1b7\r") and SCP_RTL.endswith("\x1b8")


def test_next_row_is_independent():
    assert run("سلام\nabc\n".encode()) == f"{SCP_RTL}سلام\n{SCP_DEFAULT}abc\n"


def test_vertical_move_ends_row():
    assert run("سلام\x1b[2Babc".encode()) == f"{SCP_RTL}سلام\x1b[2B{SCP_DEFAULT}abc"


def test_idle_flush_midrow_never_flips_back():
    t = Transformer()
    a = t.feed("سلام".encode()) + t.flush()
    b = t.feed(b" abc") + t.flush()
    assert a == f"{SCP_RTL}سلام" and b == " abc"


def test_split_bytes_across_reads():
    t = Transformer()
    raw = "\x1b[31mسلام\n".encode()
    assert "".join(t.feed(raw[i:i + 1]) for i in range(len(raw))) == f"\x1b[31m{SCP_RTL}سلام\n"


def test_osc_title_sequences_pass_through():
    assert run("\x1b]0;عنوان\x07x\n".encode()) == f"\x1b]0;عنوان\x07{SCP_DEFAULT}x\n"


def test_off_mode_is_passthrough():
    assert run("سلام\n".encode(), "off") == "سلام\n"


def test_other_rtl_scripts_detected():
    assert is_rtl("ש") and is_rtl("م") and is_rtl("ܐ") and is_rtl("ދ")
    assert not is_rtl("a") and not is_rtl("1") and not is_rtl("‌")  # ZWNJ is neutral
    assert run("שלום world\n".encode()) == f"{SCP_RTL}שלום world\n"


def test_no_row_flips_back_to_ltr_in_a_claude_style_frame():
    # synthetic frame in the shape Claude Code really emits (captured with --log)
    words = ["امروز", "صبح", "cup", "of", "coffee", "رفتم", "کار"]
    frame = "\x1b[H\r\x1b[2C\x1b[8B" + "".join(f"\x1b[{3 + 5 * i}G{w}" for i, w in enumerate(words)) + "\r\x1b[2B"
    out = run(frame.encode())
    for row in re.split(r"\x1b\[\d*[ABEFH]", out):
        if SCP_RTL in row:
            assert SCP_DEFAULT not in row[row.index(SCP_RTL):]
