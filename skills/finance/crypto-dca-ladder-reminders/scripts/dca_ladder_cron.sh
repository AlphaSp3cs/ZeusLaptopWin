#!/bin/bash
# Weekly DCA ladder: refresh live tape FIRST, then evaluate tranches.
cd "$HOME" || exit 1
python3 dca_tape_refresh.py > "$HOME/dca_tape_refresh_last.log" 2>&1
python3 dca_ladder_check.py --quiet 2>&1
