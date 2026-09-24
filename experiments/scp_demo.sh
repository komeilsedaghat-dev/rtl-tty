#!/usr/bin/env bash
# Reproduces the findings behind rtl-tty. Run it in a VTE terminal (GNOME Terminal,
# Tilix, ...) and compare how the same sentence is laid out in each case.
#
# SCP direction persists on the following rows, so every label and every case first
# resets to the terminal default (CSI 0 SPACE k) while the cursor is in column 0.
#
# Observed in GNOME Terminal (VTE 0.76): (2), (3), (4) right-aligned with correct order;
# (1) and (5) left-aligned and scrambled (so bidi control characters are ignored).
# (6) and (7) use a row that ALREADY has text: it is printed left-to-right, the cursor goes
# back up, SCP is sent (column 1 in case 6, column 0 in case 7) and the row is rewritten.
# Observed: (6) stays left-aligned and scrambled, (7) becomes right-to-left. So on an
# existing row SCP is only honoured in column 0.
S='این یه test با English وسط جمله بود'
ESC=$'\e'
reset() { printf '%s[0 k' "$ESC"; }
label() { reset; printf '%s\n' "$1"; reset; }

label "1) default (no direction set)"
printf '%s\n' "$S"

label "2) SCP right-to-left, cursor at column 0"
printf '%s[2 k%s\n' "$ESC" "$S"

label "3) 2-column indent, then save cursor -> column 0 -> SCP -> restore (what rtl-tty does)"
printf '%s[2C%s7\r%s[2 k%s8%s\n' "$ESC" "$ESC" "$ESC" "$ESC" "$S"

label "4) 2-column indent, SCP sent right there (cursor in column 2)"
printf '%s[2C%s[2 k%s\n' "$ESC" "$ESC" "$S"

label "5) Unicode bidi control characters (RLI ... PDI) instead of SCP"
printf '\xe2\x81\xa7%s\xe2\x81\xa9\n' "$S"


label "6) row already written LTR; go back, send SCP in column 1, rewrite the row"
printf '%s\n' "$S"
printf '%s[A\r%s[C%s[2 k\r%s\n' "$ESC" "$ESC" "$ESC" "$S"

label "7) row already written LTR; go back, send SCP in column 0, rewrite the row"
printf '%s\n' "$S"
printf '%s[A\r%s[2 k%s\n' "$ESC" "$ESC" "$S"

reset
