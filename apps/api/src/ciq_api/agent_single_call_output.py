"""Prepared private pipes and bounded capture; no process or admission authority.

The trusted host retains this object before preparation/allocation, serializes
all calls and never closes/reuses its descriptors independently. Writer handoff
is one-shot even after a lost launch acknowledgment. This is not PreparedHost.
"""

import errno
import os
import stat
from dataclasses import dataclass, field

from ciq_api.agent_single_call_supervisor import READY

ERROR = "single_call_output_unavailable"
LIMIT = 128


def require(value):
    if not value:
        raise ValueError(ERROR)


@dataclass
class _Pipe:
    reader: int | None
    writer: int | None
    reader_identity: tuple[int, int] | None = None
    writer_identity: tuple[int, int] | None = None
    raw: bytes = field(default=b"", repr=False)
    eof: bool = False


@dataclass(frozen=True)
class CapturedOutput:
    stdout: bytes = field(repr=False)
    stderr: bytes = field(repr=False)
    drained: bool


class OwnedSingleCallOutput:
    """Original separate pipes, fixed work/memory per observation, terminal faults.

    take_writers() returns only the original descriptors, once, before the
    trusted caller attempts allocation. release_writers() closes the host's
    copies after that attempt, including exceptions. Neither is a launch ACK.
    Closing pipes never proves process cleanup; the host must kill the original
    cgroup and collect its bootstrap waiter independently after every failure.
    """

    def __init__(self, role):
        require(type(role) is str and role in READY)
        self._marker = READY[role]
        self._pipes: list[_Pipe] = []
        self._used = self._ready = self._offered = self._released = False
        self._failed = self._closed = False

    def _healthy(self):
        require(self._ready and not self._failed and not self._closed)

    def _verify(self, pipe, fd, *, reader):
        info = os.fstat(fd)
        require(stat.S_ISFIFO(info.st_mode)
                and (info.st_dev, info.st_ino) == (
                    pipe.reader_identity if reader else pipe.writer_identity)
                and not os.get_inheritable(fd) and os.get_blocking(fd) is (not reader))

    def prepare(self):
        require(not self._used and not self._closed)
        self._used = True
        try:
            for _ in range(2):
                # Python creates non-inheritable descriptors. Retain both before
                # subsequent operations can fail; never accept external pipes.
                pipe = _Pipe(*os.pipe())
                self._pipes.append(pipe)
                for attribute in ("reader", "writer"):
                    info = os.fstat(getattr(pipe, attribute))
                    setattr(pipe, attribute + "_identity", (info.st_dev, info.st_ino))
                os.set_blocking(pipe.reader, False)
                self._verify(pipe, pipe.reader, reader=True)
                self._verify(pipe, pipe.writer, reader=False)
            require(self._pipes[0].reader_identity != self._pipes[1].reader_identity
                    and self._pipes[0].writer_identity != self._pipes[1].writer_identity)
            self._ready = True
        except BaseException as error:
            self._failed = True
            self.close()
            if isinstance(error, Exception):
                raise ValueError(ERROR) from None
            raise

    def take_writers(self):
        self._healthy()
        require(not self._offered)
        self._offered = True  # Consume before validation/return, never reconstruct.
        try:
            for pipe in self._pipes:
                self._verify(pipe, pipe.reader, reader=True)
                self._verify(pipe, pipe.writer, reader=False)
            return tuple(pipe.writer for pipe in self._pipes)
        except BaseException as error:
            self._failed = True
            if isinstance(error, Exception):
                raise ValueError(ERROR) from None
            raise

    def release_writers(self):
        # Attempt both closes even after one fails. A lost close ACK is terminal;
        # remove each descriptor from ownership before closing, never retry it.
        self._healthy()
        require(self._offered)
        if self._released:
            return
        self._released = True
        clean = True
        interrupted = None
        for pipe in self._pipes:
            fd = pipe.writer
            try:
                self._verify(pipe, fd, reader=False)
                pipe.writer = None
                os.close(fd)
            except BaseException as error:
                clean = False
                if not isinstance(error, Exception) and interrupted is None:
                    interrupted = error
        if not clean:
            self._failed = True
            if interrupted is not None:
                raise interrupted
            raise ValueError(ERROR) from None

    def observe(self):
        self._healthy()
        require(self._offered and self._released)
        try:
            for index, pipe in enumerate(self._pipes):
                self._verify(pipe, pipe.reader, reader=True)
                if not pipe.eof:
                    try:
                        # One nonblocking read per stream, no drain/retry loop.
                        raw = os.read(pipe.reader, LIMIT + 1 - len(pipe.raw))
                    except BlockingIOError as error:
                        require(error.errno in (errno.EAGAIN, errno.EWOULDBLOCK))
                        continue
                    require(len(pipe.raw) + len(raw) <= LIMIT)
                    if not raw:
                        pipe.eof = True
                    combined = pipe.raw + raw
                    # Do not retain arbitrary diagnostics or untrusted payloads.
                    require((index == 0 and self._marker.startswith(combined))
                            or (index == 1 and not combined))
                    pipe.raw = combined
            output, diagnostic = self._pipes
            require(not output.eof or output.raw == self._marker)
            return CapturedOutput(
                self._marker if output.raw == self._marker else b"", b"",
                output.eof and diagnostic.eof,
            )
        except BaseException as error:
            self._failed = True
            if isinstance(error, Exception):
                raise ValueError(ERROR) from None
            raise

    def close(self):
        # Only retire descriptors still matching the original pipe identity.
        # No wait, signal, history reset or claim of descendant cleanup.
        self._closed = True
        for pipe in self._pipes:
            for attribute in ("reader", "writer"):
                fd = getattr(pipe, attribute)
                setattr(pipe, attribute, None)
                if fd is not None:
                    try:
                        info = os.fstat(fd)
                        identity = getattr(pipe, attribute + "_identity")
                        if identity is None or (info.st_dev, info.st_ino) == identity:
                            os.close(fd)
                    except OSError:
                        pass
