"""rtl-tty: run a command inside a PTY and fix RTL (Persian/Arabic/Hebrew) rendering."""
import fcntl
import os
import pty
import select
import signal
import sys
import termios
import tty

from . import __version__
from .transform import Transformer

USAGE = """usage: rtl-tty [--mode scp|off] [--log FILE] COMMAND [ARGS...]

Runs COMMAND in a pseudo-terminal and marks every output row that contains
right-to-left text so the terminal lays it out right-to-left.

  --mode scp|off   scp (default) fixes rows; off passes output through (for A/B tests)
  --log FILE       append raw child output and transformed output to FILE (debugging;
                   the log contains everything shown on screen)
  --version        print version
  -h, --help       this text

example: rtl-tty claude
"""


def _write_all(fd, data):
    while data:
        data = data[os.write(fd, data):]


def _set_winsize(fd, src):
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, fcntl.ioctl(src, termios.TIOCGWINSZ, b"\0" * 8))
    except OSError:
        pass


def _parse(argv):
    mode, log = "scp", os.environ.get("RTL_TTY_LOG")
    while argv and argv[0].startswith("-"):
        a = argv.pop(0)
        if a in ("-h", "--help"):
            print(USAGE, end=""); sys.exit(0)
        elif a == "--version":
            print(f"rtl-tty {__version__}"); sys.exit(0)
        elif a == "--mode" and argv:
            mode = argv.pop(0)
        elif a == "--log" and argv:
            log = argv.pop(0)
        else:
            sys.exit(f"rtl-tty: unknown option {a}\n\n{USAGE}")
    if not argv or mode not in ("scp", "off"):
        sys.exit(USAGE)
    return mode, log, argv


def main(argv=None):
    mode, log_path, cmd = _parse(list(sys.argv[1:] if argv is None else argv))
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        os.execvp(cmd[0], cmd)  # not interactive: nothing to fix, get out of the way

    pid, master = pty.fork()
    if pid == 0:
        try:
            os.execvp(cmd[0], cmd)
        except OSError as e:
            sys.exit(f"rtl-tty: cannot run {cmd[0]}: {e.strerror}")
    out_fd, in_fd = sys.stdout.fileno(), sys.stdin.fileno()
    _set_winsize(master, out_fd)
    signal.signal(signal.SIGWINCH, lambda *_: (_set_winsize(master, out_fd), os.kill(pid, signal.SIGWINCH)))

    saved = termios.tcgetattr(in_fd)
    tty.setraw(in_fd)
    tf = Transformer(mode)
    log = open(log_path, "a") if log_path else None
    try:
        while True:
            try:
                ready, _, _ = select.select([master, in_fd], [], [], 0.03)
            except InterruptedError:
                continue
            if not ready:
                text = tf.flush()
                if text:
                    _write_all(out_fd, text.encode())
                continue
            if in_fd in ready:
                data = os.read(in_fd, 4096)
                if data:
                    _write_all(master, data)
            if master in ready:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    data = b""
                if not data:
                    break
                text = tf.feed(data)
                if log:
                    log.write("IN  %r\nOUT %r\n" % (data, text)); log.flush()
                if text:
                    _write_all(out_fd, text.encode())
    finally:
        termios.tcsetattr(in_fd, termios.TCSADRAIN, saved)
    _, status = os.waitpid(pid, 0)
    sys.exit(os.waitstatus_to_exitcode(status))
