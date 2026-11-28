"""Bounded CI failure progress never prints parameters or private trace content."""

import pytest

from scripts.test_agent_receipt_peer import summary


def test_timeout_reports_only_completed_count_and_static_module(capfd):
    output = (
        b"apps/api/tests/test_agent_single_call_identity_linux.py::test_identity[provider] "
        b"PASSED [  1%]\nPRIVATE_CREDENTIAL\n"
        b"apps/api/tests/test_agent_single_call_identity_linux.py::test_identity[custody] "
        b"PASSED [  2%]\n"
    )
    assert summary(output) is None
    captured = capfd.readouterr()
    assert captured.out == (
        "Completed 2 disposable checks; last module test_agent_single_call_identity_linux.py\n"
    ) and not captured.err


def test_finished_summary_and_terminal_escape_handling(capfd):
    assert summary(b"\x1b[32m66 passed in 301.00s (0:05:01)\x1b[0m\n") == 66
    assert capfd.readouterr().out == "66 passed in 301.00s (0:05:01)\n"


@pytest.mark.parametrize("counts", ["66 passed", "66 passed, 1 warning"])
def test_verbose_pytest_summary_with_separators(capfd, counts):
    output = f"\x1b[32m================= {counts} in 320.12s (0:05:20) =================\x1b[0m\n"
    assert summary(output.encode()) == 66
    assert capfd.readouterr().out == f"{counts} in 320.12s (0:05:20)\n"


def test_mixed_failure_summary_cannot_be_accepted(capfd):
    assert summary(b"================= 1 failed, 65 passed in 320.12s =================\n") is None
    assert capfd.readouterr().out == ""


def test_unknown_progress_cannot_print_injected_paths_or_parameters(capfd):
    assert summary(b"/private/credentials.py::test[PRIVATE] PASSED [ 1%]\n") is None
    assert capfd.readouterr().out == ""
