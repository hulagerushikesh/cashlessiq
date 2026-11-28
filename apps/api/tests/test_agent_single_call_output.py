"""Actual private pipes; no processes, network, database or cgroup mutation."""

import errno
import os
from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from ciq_api import agent_single_call_output as m


@contextmanager
def captured(role="receipt"):
    output = m.OwnedSingleCallOutput(role)
    writers = []
    try:
        output.prepare()
        writers = [os.dup(fd) for fd in output.take_writers()]
        output.release_writers()
        yield output, writers
    finally:
        for fd in writers:
            if fd is not None:
                os.close(fd)
        output.close()


def end(writers, index):
    fd, writers[index] = writers[index], None
    os.close(fd)


@pytest.mark.parametrize("role", ["receipt", "provider", "custody"])
def test_split_marker_hidden_until_complete_and_both_eofs_required(role):
    with captured(role) as (output, writers):
        marker = m.READY[role]
        assert output.observe() == m.CapturedOutput(b"", b"", False)
        for byte in marker:
            os.write(writers[0], bytes([byte]))
            snapshot = output.observe()
            assert snapshot.stderr == b"" and not snapshot.drained
            assert snapshot.stdout in (b"", marker)
        assert snapshot.stdout == marker
        end(writers, 0)
        assert not output.observe().drained
        end(writers, 1)
        assert output.observe() == m.CapturedOutput(marker, b"", True)
        assert output.observe() == m.CapturedOutput(marker, b"", True)
        assert marker.decode().strip() not in repr(snapshot)


@pytest.mark.parametrize("role", [None, 53002, "root", "../provider", "receipt\n"])
def test_roles_are_fixed_and_never_command_or_path_selectors(role):
    with pytest.raises(ValueError, match=m.ERROR):
        m.OwnedSingleCallOutput(role)


def test_writers_are_separate_private_blocking_pipes_and_handoff_is_once():
    output = m.OwnedSingleCallOutput("receipt")
    try:
        output.prepare()
        writers = output.take_writers()
        assert len(set(writers)) == 2
        assert all(os.get_blocking(fd) and not os.get_inheritable(fd) for fd in writers)
        assert os.fstat(writers[0]).st_ino != os.fstat(writers[1]).st_ino
        with pytest.raises(ValueError, match=m.ERROR):
            output.take_writers()
        with pytest.raises(ValueError, match=m.ERROR):
            output.prepare()
        output.release_writers()
        output.release_writers()
        with pytest.raises(ValueError, match=m.ERROR):
            output.observe()  # Empty EOF cannot acknowledge readiness.
    finally:
        output.close()
        output.close()


@pytest.mark.parametrize("phase", ["unprepared", "unoffered", "unreleased", "closed"])
def test_no_observation_before_handoff_and_release_or_after_close(phase):
    output = m.OwnedSingleCallOutput("custody")
    try:
        if phase != "unprepared":
            output.prepare()
        if phase in ("unreleased", "closed"):
            output.take_writers()
        if phase == "closed":
            output.release_writers()
            output.close()
        with pytest.raises(ValueError, match=m.ERROR):
            output.observe()
    finally:
        output.close()


@pytest.mark.parametrize("data", [b"PRIVATE", b"\xff", b"single_call_provider_ready\n",
                                   b"single_call_receipt_ready\nEXTRA", b"X" * 1024])
def test_unexpected_or_excess_output_is_terminal_and_redacted(data):
    with captured() as (output, writers):
        os.write(writers[0], data)
        with pytest.raises(ValueError) as caught:
            output.observe()
        assert str(caught.value) == m.ERROR and caught.value.__cause__ is None
        assert sum(len(pipe.raw) for pipe in output._pipes) <= m.LIMIT
        with pytest.raises(ValueError, match=m.ERROR):
            output.observe()  # Never recover by draining to later valid output.


def test_stderr_is_rejected_even_after_valid_readiness():
    with captured() as (output, writers):
        os.write(writers[0], m.READY["receipt"])
        assert output.observe().stdout == m.READY["receipt"]
        os.write(writers[1], b"PRIVATE TOKEN diagnostic")
        with pytest.raises(ValueError) as caught:
            output.observe()
        assert str(caught.value) == m.ERROR
        assert output._pipes[1].raw == b""
        with pytest.raises(ValueError, match=m.ERROR):
            output.observe()


def test_output_after_acknowledged_marker_is_terminal():
    with captured() as (output, writers):
        os.write(writers[0], m.READY["receipt"])
        assert output.observe().stdout == m.READY["receipt"]
        os.write(writers[0], b"\n")
        with pytest.raises(ValueError, match=m.ERROR):
            output.observe()


@pytest.mark.parametrize("prefix", [b"", b"s", b"single_call_receipt_ready"])
def test_eof_with_missing_or_incomplete_marker_is_terminal(prefix):
    with captured() as (output, writers):
        os.write(writers[0], prefix)
        end(writers, 0)
        if prefix:
            output.observe()
        with pytest.raises(ValueError, match=m.ERROR):
            output.observe()


def test_nonblocking_fixed_read_budget_without_waiting_for_eof(monkeypatch):
    with captured() as (output, writers):
        read = Mock(wraps=os.read)
        monkeypatch.setattr(m.os, "read", read)
        assert not output.observe().drained
        assert read.call_count == 2
        assert [call.args[1] for call in read.call_args_list] == [129, 129]
        os.write(writers[0], b"single_")
        output.observe()
        read.reset_mock()
        output.observe()
        assert read.call_count == 2
        assert [call.args[1] for call in read.call_args_list] == [122, 129]


@pytest.mark.parametrize("change", ["blocking", "inheritable", "replaced", "closed"])
def test_changed_original_reader_is_terminal_and_close_preserves_replacement(change):
    with captured() as (output, _writers):
        fd = output._pipes[0].reader
        replacement = None
        try:
            if change == "blocking":
                os.set_blocking(fd, True)
            elif change == "inheritable":
                os.set_inheritable(fd, True)
            elif change == "closed":
                os.close(fd)
            else:
                replacement = os.open(os.devnull, os.O_RDONLY)
                os.dup2(replacement, fd, inheritable=False)
            with pytest.raises(ValueError, match=m.ERROR):
                output.observe()
            output.close()
            if change == "replaced":
                assert os.fstat(fd).st_ino == os.fstat(replacement).st_ino
                os.close(fd)
        finally:
            if replacement is not None:
                os.close(replacement)


@pytest.mark.parametrize("failure", [OSError(errno.EIO, "PRIVATE"), InterruptedError(),
                                      BlockingIOError(errno.EBADF, "PRIVATE"), KeyboardInterrupt()])
def test_read_fault_or_cancellation_consumes_capture(monkeypatch, failure):
    with captured() as (output, _writers):
        monkeypatch.setattr(m.os, "read", Mock(side_effect=failure))
        expected = KeyboardInterrupt if isinstance(failure, KeyboardInterrupt) else ValueError
        with pytest.raises(expected):
            output.observe()
        with pytest.raises(ValueError, match=m.ERROR):
            output.observe()


@pytest.mark.parametrize("failure", [OSError("PRIVATE"), KeyboardInterrupt()])
def test_writer_close_uncertainty_attempts_both_and_never_retries(monkeypatch, failure):
    output = m.OwnedSingleCallOutput("custody")
    output.prepare()
    writers = output.take_writers()
    close = os.close
    calls = []
    def uncertain(fd):
        calls.append(fd)
        close(fd)
        if fd == writers[0]:
            raise failure
    try:
        monkeypatch.setattr(m.os, "close", uncertain)
        expected = KeyboardInterrupt if isinstance(failure, KeyboardInterrupt) else ValueError
        with pytest.raises(expected):
            output.release_writers()
        assert calls == list(writers)
        with pytest.raises(ValueError, match=m.ERROR):
            output.release_writers()
        assert calls == list(writers)
    finally:
        output.close()
    assert all(calls.count(fd) == 1 for fd in writers)


def test_partial_pipe_preparation_failure_retires_owned_fds(monkeypatch):
    output = m.OwnedSingleCallOutput("receipt")
    pipe = os.pipe
    created = []
    def allocate():
        if created:
            raise OSError("PRIVATE")
        created.extend(pipe())
        return tuple(created)
    monkeypatch.setattr(m.os, "pipe", allocate)
    with pytest.raises(ValueError, match=m.ERROR):
        output.prepare()
    for fd in created:
        with pytest.raises(OSError):
            os.fstat(fd)
    with pytest.raises(ValueError, match=m.ERROR):
        output.prepare()
    output.close()


def test_writer_validation_failure_still_allows_original_descriptor_retirement():
    output = m.OwnedSingleCallOutput("provider")
    try:
        output.prepare()
        writers = output.take_writers()
        os.set_inheritable(writers[0], True)
        with pytest.raises(ValueError, match=m.ERROR):
            output.release_writers()
        output.close()
        for fd in writers:
            with pytest.raises(OSError):
                os.fstat(fd)
    finally:
        output.close()
