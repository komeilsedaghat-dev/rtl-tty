import subprocess, sys, pty, os, select


def test_version_and_help():
    r = subprocess.run([sys.executable, "-m", "rtl_tty", "--version"], capture_output=True, text=True)
    assert r.stdout.startswith("rtl-tty ")
    r = subprocess.run([sys.executable, "-m", "rtl_tty", "--help"], capture_output=True, text=True)
    assert "usage: rtl-tty" in r.stdout


def test_no_command_is_an_error():
    r = subprocess.run([sys.executable, "-m", "rtl_tty"], capture_output=True, text=True)
    assert r.returncode != 0


def test_passes_through_and_marks_rows_in_a_real_pty():
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp(sys.executable, [sys.executable, "-m", "rtl_tty", "printf", "hi سلام\\n"])
    buf = b""
    while True:
        r, _, _ = select.select([fd], [], [], 5)
        if not r:
            break
        try:
            d = os.read(fd, 4096)
        except OSError:
            break
        if not d:
            break
        buf += d
    os.waitpid(pid, 0)
    assert b"\x1b[2 k" in buf and "سلام".encode() in buf


def test_exit_code_is_propagated():
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp(sys.executable, [sys.executable, "-m", "rtl_tty", "sh", "-c", "exit 7"])
    while True:
        try:
            if not os.read(fd, 1024):
                break
        except OSError:
            break
    _, st = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(st) == 7
