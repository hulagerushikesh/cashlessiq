"""Bounded CI failure progress never prints parameters or private trace content."""

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


def test_unknown_progress_cannot_print_injected_paths_or_parameters(capfd):
    assert summary(b"/private/credentials.py::test[PRIVATE] PASSED [ 1%]\n") is None
    assert capfd.readouterr().out == ""
