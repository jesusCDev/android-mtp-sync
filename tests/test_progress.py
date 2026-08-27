"""Progress output stays line-based when stdout is not a terminal.

The web UI captures stdout through a line-buffered stand-in, so a stream of
'\\r'-terminated animation frames would pile up into one enormous line that is
then persisted to run history.
"""

import io
import sys

from phone_migration import progress


def test_a_rule_progress_cycle_writes_at_most_two_plain_lines_off_a_tty(monkeypatch):
    buffer = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buffer)

    rule_progress = progress.RuleProgress("r-1", "copy", 1, 1)
    rule_progress.start()
    rule_progress.stop(success=True, summary="3 files")

    output = buffer.getvalue()
    assert "\r" not in output
    assert 0 < len(output.splitlines()) <= 2


def test_the_progress_bar_is_silent_off_a_tty_until_the_last_frame(monkeypatch):
    buffer = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buffer)

    progress.print_progress_bar(1, 3, prefix="Overall Progress:")
    assert buffer.getvalue() == ""

    progress.print_progress_bar(3, 3, prefix="Overall Progress:")
    output = buffer.getvalue()
    assert "\r" not in output
    assert len(output.splitlines()) == 1
