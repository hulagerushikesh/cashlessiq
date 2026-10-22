"""Runner safety/failure regression tests; actual Linux evidence is opt-in only."""

import ast
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import test_supervisor_container as runner


class DockerFixture:
    def __init__(self, fault):
        self.fault = fault
        self.container = None
        self.image = None
        self.calls = []

    def run(self, command, **kwargs):
        assert command[0] == "docker"
        assert kwargs["timeout"] <= 900
        args = command[1:]
        self.calls.append(args)
        output = ""
        if args[0] == "build":
            self.image = args[args.index("-t") + 1]
            assert set(p.name for p in Path(args[-1]).iterdir()) == set(runner.SOURCES)
            if self.fault == "build":
                raise subprocess.CalledProcessError(1, command)
        elif args[0] == "create":
            self.container = args[args.index("--name") + 1]
            assert args[args.index("--network") + 1] == "none"
            assert not any(a in args for a in ("--mount", "-v", "--privileged", "-p"))
            if self.fault == "create":
                raise subprocess.CalledProcessError(1, command)
        elif args[0] == "inspect":
            value = {
                "HostConfig": {
                    "NetworkMode": "none",
                    "ReadonlyRootfs": True,
                    "CapDrop": ["ALL"],
                    "Privileged": False,
                    "PortBindings": {},
                },
                "Config": {"User": "10001:10001"},
                "Mounts": [],
            }
            if self.fault == "network":
                value["HostConfig"]["NetworkMode"] = "bridge"
            if self.fault == "mount":
                value["Mounts"] = [{"Source": "/unexpected"}]
            output = json.dumps([value])
        elif args[0] == "wait":
            if self.fault == "timeout":
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            output = "1" if self.fault == "exit" else "0"
        elif args[0] == "logs":
            cases = sorted(runner.CASES)
            if self.fault == "missing":
                cases.pop()
            if self.fault == "duplicate":
                cases[-1] = cases[0]
            output = "\n".join(json.dumps({"case": c, "status": "PASS"}) for c in cases)
        elif args[0] == "ps":
            output = self.container or ""
        elif args[0] == "rm":
            assert args == ["rm", "-f", self.container]
            self.container = None
        elif args[:2] == ["image", "ls"]:
            output = self.image or ""
        elif args[:2] == ["image", "rm"]:
            assert args[2] == self.image
            self.image = None
        return SimpleNamespace(stdout=output)


@pytest.mark.parametrize(
    "fault",
    [None, "build", "create", "network", "mount", "timeout", "exit", "missing", "duplicate"],
)
def test_bounded_runner_cleans_exact_resources_on_success_and_failure(monkeypatch, fault):
    fixture = DockerFixture(fault)
    monkeypatch.setattr(runner.subprocess, "run", fixture.run)
    if fault is None:
        runner.main()
    else:
        with pytest.raises((AssertionError, subprocess.SubprocessError)):
            runner.main()
    assert fixture.container is None
    assert fixture.image is None
    assert not any("prune" in call for call in fixture.calls)
    if fault in ("network", "mount"):
        assert not any(call[0] == "start" for call in fixture.calls)


def test_probe_and_build_context_are_test_only():
    root = runner.ROOT
    assert set(runner.SOURCES) == {"Dockerfile", "supervisor_probe.py", "offline_supervisor.py"}
    dockerfile = runner.SOURCES["Dockerfile"].read_text()
    assert "COPY offline_supervisor.py supervisor_probe.py /probe/" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert not any(word in dockerfile for word in ("pip ", "uv ", "ciq_api.main", "ADD "))
    tree = ast.parse((root / "scripts/supervisor_probe.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        assert not any(n.startswith(("snowflake", "ciq_api", "sqlalchemy")) for n in names)
    for project in ("api", "worker", "membership"):
        assert "supervisor_probe" not in (root / f"apps/{project}/Dockerfile").read_text()
