"""Stream transform that tells the terminal which output rows are right-to-left.

VTE (GNOME Terminal, Tilix, ...) lays every row out left-to-right by default and
*discards* Unicode bidi control characters (RLI/PDI/RLM). Its own mechanism is
SCP ("select character path", CSI 2 SPACE k = right-to-left), which it honours
only while the cursor is in column 0. Full-screen apps such as Claude Code
indent rows and write each word with an absolute column move (CSI n G), so we:

  * buffer a row until the cursor leaves it (newline or vertical move),
  * classify the whole row once (any RTL letter -> RTL),
  * insert  ESC 7, CR, SCP, ESC 8  before the row's first text
    (save cursor, go to column 0, set direction, restore cursor).

flush() pushes out a partial row when the child goes idle so typing stays live.
"""
import codecs

SCP_RTL = "\x1b7\r\x1b[2 k\x1b8"
SCP_DEFAULT = "\x1b7\r\x1b[0 k\x1b8"
VERTICAL_FINALS = frozenset("ABEFHfd")  # CSI finals that move to another row

# Hebrew, Arabic (+ supplement/extended/presentation forms), Syriac, Thaana, NKo
_RTL_RANGES = (
    (0x0590, 0x08FF), (0xFB1D, 0xFDFF), (0xFE70, 0xFEFF),
    (0x10800, 0x10FFF), (0x1E800, 0x1EFFF),
)


def is_rtl(ch):
    o = ord(ch)
    return any(a <= o <= b for a, b in _RTL_RANGES)


class Transformer:
    def __init__(self, mode="scp"):
        self.mode = mode
        self.dec = codecs.getincrementaldecoder("utf-8")("replace")
        self.pending = ""
        self.seg = []      # tokens of the current row: (is_text, str)
        self.sent = None   # direction already sent for this row (after a partial flush)

    def _emit(self, tail=""):
        toks, self.seg = self.seg, []
        if self.mode == "off" or not any(t for t, _ in toks):
            return "".join(s for _, s in toks) + tail
        rtl = any(is_rtl(c) for t, s in toks if t for c in s)
        want = "rtl" if rtl else "ltr"
        out, marked = [], False
        for is_text, s in toks:
            if is_text and not marked:
                marked = True
                if self.sent is None or (want == "rtl" and self.sent != "rtl"):
                    out.append(SCP_RTL if rtl else SCP_DEFAULT)
                    self.sent = want
            out.append(s)
        out.append(tail)
        return "".join(out)

    def feed(self, data):
        """Take child output (bytes), return text to write to the terminal."""
        self.pending += self.dec.decode(data)
        s, i, out = self.pending, 0, []
        while i < len(s):
            c = s[i]
            if c == "\n":
                out.append(self._emit(c)); self.sent = None; i += 1
            elif c == "\x1b":
                if i + 1 >= len(s):
                    break
                n = s[i + 1]
                if n == "[":
                    j = i + 2
                    while j < len(s) and not ("@" <= s[j] <= "~"):
                        j += 1
                    if j >= len(s):
                        break
                    if s[j] in VERTICAL_FINALS:
                        out.append(self._emit(s[i:j + 1])); self.sent = None
                    else:
                        self.seg.append((False, s[i:j + 1]))
                    i = j + 1
                elif n == "]":
                    j = i + 2
                    while j < len(s) and s[j] != "\x07" and not (s[j] == "\x1b" and s[j + 1:j + 2] == "\\"):
                        j += 1
                    if j >= len(s):
                        break
                    j += 1 if s[j] == "\x07" else 2
                    self.seg.append((False, s[i:j])); i = j
                else:
                    self.seg.append((False, s[i:i + 2])); i += 2
            elif c < " ":
                self.seg.append((False, c)); i += 1
            else:
                self.seg.append((True, c)); i += 1
        self.pending = s[i:]
        return "".join(out)

    def flush(self):
        """Emit the current partial row (call when the child has gone idle)."""
        return self._emit() if self.seg else ""
