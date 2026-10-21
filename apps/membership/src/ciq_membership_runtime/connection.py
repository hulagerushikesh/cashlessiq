"""Explicit, inactive membership-only connection boundary; no secret discovery."""

import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from pathlib import PurePosixPath

from ciq_api.worker_authority import WorkerDenied
from sqlalchemy import URL, create_engine
from sqlalchemy.pool import NullPool

_PRIVATE = tuple(IPv4Network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,62}")


@dataclass(frozen=True, slots=True, repr=False)
class MembershipDatabaseConfig:
    """Trusted injection only. Repr intentionally excludes every field."""

    host: str
    hostaddr: str
    port: int
    database: str
    username: str
    password: str
    ca_file: str

    def __post_init__(self):
        try:
            if (
                type(self.host) is not str
                or len(self.host) > 253
                or not self.host.isascii()
                or not all(_LABEL.fullmatch(label) for label in self.host.split("."))
            ):
                raise ValueError
            # DNS identity must not itself be an IP literal.
            if all(label.isdigit() for label in self.host.split(".")):
                raise ValueError
            address = IPv4Address(self.hostaddr)
            if type(self.hostaddr) is not str or str(address) != self.hostaddr:
                raise ValueError
            if not any(address in network for network in _PRIVATE):
                raise ValueError
            if type(self.port) is not int or not 1 <= self.port <= 65535:
                raise ValueError
            for value in (self.database, self.username):
                if type(value) is not str or not _IDENTIFIER.fullmatch(value):
                    raise ValueError
            if (
                type(self.password) is not str
                or not 1 <= len(self.password) <= 4096
                or "\x00" in self.password
            ):
                raise ValueError
            if (
                type(self.ca_file) is not str
                or not self.ca_file.startswith("/")
                or self.ca_file.startswith("//")
                or len(self.ca_file) > 4096
                or any(ord(char) < 32 or ord(char) == 127 for char in self.ca_file)
                or ".." in PurePosixPath(self.ca_file).parts
                or str(PurePosixPath(self.ca_file)) != self.ca_file
                or self.ca_file == "/"
            ):
                raise ValueError
        except Exception:
            raise ValueError("Invalid membership database configuration") from None

    def __repr__(self):
        return "MembershipDatabaseConfig(<redacted>)"


class MembershipConnectionFactory:
    """Fresh connections only; not imported or constructed by normal startup.

    A dedicated process with immutable environment is required. Ambient PG*
    variables cause denial rather than being interpreted or temporarily removed.
    File custody/readiness and whole-operation deadlines remain separate gates.
    """

    __slots__ = ("_engine",)

    def __init__(self, config: MembershipDatabaseConfig):
        if type(config) is not MembershipDatabaseConfig:
            raise ValueError("Invalid membership database configuration")
        try:
            self._engine = create_engine(
                URL.create(
                    "postgresql+psycopg",
                    username=config.username,
                    password=config.password,
                    host=config.host,
                    port=config.port,
                    database=config.database,
                ),
                connect_args={
                    "hostaddr": config.hostaddr,
                    "sslmode": "verify-full",
                    "sslrootcert": config.ca_file,
                    "ssl_min_protocol_version": "TLSv1.3",
                    "gssencmode": "disable",
                    "connect_timeout": 2,
                    "options": "-csearch_path=",
                    "passfile": "/dev/null",
                    "sslcertmode": "disable",
                    "application_name": "ciq-membership",
                },
                poolclass=NullPool,
                echo=False,
                hide_parameters=True,
            )
        except Exception:
            raise WorkerDenied("Worker access denied") from None

    def __repr__(self):
        return "MembershipConnectionFactory(<redacted>)"

    @contextmanager
    def connect(self):
        try:
            # Do not mutate global environment around libpq: concurrent threads
            # could otherwise race and consume another caller's configuration.
            if any(name.upper().startswith("PG") for name in os.environ):
                raise ValueError
            with self._engine.connect() as connection:
                yield connection
        except Exception:
            raise WorkerDenied("Worker access denied") from None

    def close(self):
        """Dispose resources explicitly; no reconnect, initialization or fallback."""
        try:
            self._engine.dispose()
        except Exception:
            raise WorkerDenied("Worker access denied") from None
