"""Opt-in fresh Linux CI ownership/handoff, never production activation.

Actual 35-resource allocator and private helpers; only generated fictional
identities. No caller DSN, host port, existing-resource adoption or artifact
publication. The disposable runner is the final owner of uncertain leftovers.
"""

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

if (
    sys.platform != "linux"
    or os.environ.get("GITHUB_ACTIONS") != "true"
    or os.environ.get("CIQ_COMPOSITION_TEST") != "1"
):
    pytest.skip("Dedicated disposable Linux composition job required", allow_module_level=True)

from composition_controller import Controller
from composition_inventory_fixture import implementation as inv
from composition_journal_fixture import implementation as ledger
from composition_launcher import Launcher
from composition_material_fixture import TLS_NAMES, bundles
from composition_physical_pki import SUBNETS
from composition_physical_pki import create as create_pki
from guard_supervisor_fixture import FixtureApproval
from pydantic import SecretStr
from test_worker_guard_mtls import assertion_key as assertion_key

from ciq_api.auth import issue_local_token
from ciq_api.offline_supervisor import (
    Binding,
    Limits,
    Ready,
    Sample,
    State,
    SupervisorDenied,
    inventory,
)
from ciq_api.source_alpha import SOURCE_TENANTS
from ciq_api.validation_worker import SummaryObservation


def owner_module(name):
    return importlib.import_module(inv.__package__ + "." + name)


resources_module = owner_module("composition_resources")
engine_module = owner_module("composition_engine")
routes = owner_module("composition_routes")
headroom_module = owner_module("composition_headroom")
database = owner_module("composition_database")
db_helpers = owner_module("composition_database_helpers")


class Unconfigured:
    """No I/O while constructing a closed command inventory."""

    def __call__(self, *args):
        raise AssertionError("Bounded engine not configured")

    execute = __call__
    permit_incarnation = __call__


class PhysicalOwner:
    def __init__(self, root, pki):
        root.chmod(0o700)
        self.root = root
        self.prefix = "ciq-comp-" + uuid4().hex[:12]
        self.deadline = time.monotonic_ns() + 660_000_000_000
        self.final_deadline = self.deadline + 60_000_000_000
        self.binary = shutil.which("docker")
        assert self.binary and Path(self.binary).is_absolute()
        self.config = root / "docker-config"
        self.config.mkdir(mode=0o700)
        self.images = {}
        for kind in (
            "worker",
            "membership",
            "broker",
            "material",
            "state",
            "db-material",
            "db-data",
            "cluster",
            "bootstrap",
        ):
            value = (Path(os.environ["RUNNER_TEMP"]) / (kind + "-image-id")).read_text().strip()
            assert re.fullmatch("sha256:[0-9a-f]{64}", value)
            self.images[kind] = value
        assert len(set(self.images.values())) == len(self.images)
        parent = root / "resources"
        parent.mkdir(mode=0o700)
        self.journal = ledger.Journal(parent, self.prefix)
        self.helpers = []
        self.auxiliaries = []
        aux_parent = root / "auxiliaries"
        aux_parent.mkdir(mode=0o700)
        self.aux_journal = ledger.Journal(aux_parent, self.prefix)
        self.launcher = self.controller = None
        headroom_engine = self.engine(headroom_module.COMMANDS, budget_ns=5_000_000_000)
        self.headroom = headroom_module.LinuxHeadroom(headroom_engine, self.deadline, root)
        collision = routes.CollisionCheck(
            self.engine(routes.COMMANDS), self.deadline, route_reader=routes.linux_host_routes
        )
        self.resources = resources_module.Resources(
            prefix=self.prefix,
            images=tuple((kind, self.images[kind]) for kind in ("worker", "membership", "broker")),
            pins=tuple((role, pki[1][name][2]) for role, name in TLS_NAMES.items()),
            subnets={edge: str(subnet) for edge, subnet in SUBNETS.items()},
            journal=self.journal,
            engine=Unconfigured(),
            headroom=self.headroom,
            collision_check=collision,
            database=True,
        )
        self.resources.engine = self.engine(self.resources.commands())
        self.plan = None

    def engine(self, commands, *, budget_ns=2_000_000_000):
        return engine_module.Engine(
            binary=self.binary,
            socket="/var/run/docker.sock",
            config=self.config,
            commands=commands,
            deadline_ns=self.deadline,
            budget_ns=budget_ns,
        )

    def docker(self, *args):
        budget = min(10, (self.final_deadline - time.monotonic_ns()) / 1e9)
        assert budget > 0, "Owned cleanup budget exhausted"
        result = subprocess.run(
            [
                self.binary,
                "--host",
                "unix:///var/run/docker.sock",
                "--config",
                str(self.config),
                *args,
            ],
            capture_output=True,
            timeout=budget,
            env={},
            check=False,
        )
        assert result.returncode == 0, "Exact owned Docker operation failed"
        return result.stdout.decode().strip()

    def row(self, kind, identifier):
        rows = json.loads(self.docker(kind, "inspect", identifier))
        assert type(rows) is list and len(rows) == 1
        return rows[0]

    def allocate(self):
        self.plan = self.resources.provision()
        assert type(self.plan) is inv.Inventory
        assert self.headroom.samples == 36
        _, retained, fenced = ledger.fold(self.journal.events)
        assert not fenced and len(retained) == 35
        assert {value[2] for value in retained.values()} == {"PRESENT"}
        assert len(self.resources.observed) == 35
        for network in self.plan.networks:
            self.plan.check_network(network.edge, self.row("network", network.identifier), {})
        print("Physical allocator: 35 resources observed through fresh Linux admission", flush=True)
        return self.plan

    def helper(self, module, cls, image, *args):
        parent = self.root / ("helpers-" + str(len(self.helpers)))
        parent.mkdir(mode=0o700)
        journal = ledger.Journal(parent, self.prefix)
        helper = getattr(owner_module(module), cls)(
            self.plan,
            *args,
            image=self.images[image],
            journal=journal,
            resources=self.journal,
            engine=Unconfigured(),
            headroom=self.headroom,
        )
        self.helpers.append(helper)
        helper.engine = self.engine(helper.commands(), budget_ns=10_000_000_000)
        print(f"Physical helper: {cls} {helper.role}", flush=True)
        assert helper.run() is True
        assert len(helper.owned) == 2
        return helper

    def prepare(self, pki, assertion_key):
        plan = self.plan
        bundle = database.prepare(plan)
        staging = self.root / "staging"
        staging.mkdir(mode=0o700)
        staged_db = database.DatabaseStaging.expected(
            "database", db_helpers.fingerprint(plan), bundle.server
        ).provision(staging, bundle.server)
        generated = bundles(
            plan,
            pki,
            assertion_key,
            local_secret="fictional-composition-local-auth-secret",
            db_config=json.loads(bundle.membership["db.json"]),
            db_ca=bundle.membership["db-ca.pem"],
        )
        self.staged = {}
        self.material_helpers = {}
        self.bundle = bundle
        for role, (spec, data) in generated.items():
            staged = spec.provision(staging, data)
            self.staged[role] = staged
            self.material_helpers[role] = self.helper(
                "composition_helpers", "Helpers", "material", staged
            )
            if role != "membership":
                self.helper("composition_state_helpers", "StateHelpers", "state", role)
        self.helper("composition_database_helpers", "DatabaseHelpers", "db-material", staged_db)
        self.helper("composition_database_data_helpers", "DatabaseDataHelpers", "db-data")
        self.helper(
            "composition_database_cluster_helpers", "DatabaseClusterHelpers", "cluster", staged_db
        )
        self.helper(
            "composition_database_bootstrap_helpers",
            "DatabaseBootstrapHelpers",
            "bootstrap",
            staged_db,
        )
        assert len(self.helpers) == 19
        # Every initializer has a separate restricted read-back and durable exit.
        assert sum(len(helper.owned) for helper in self.helpers) == 38

    def attest_auxiliary(self, spec, cid):
        row = self.row("container", cid)
        assert row["Id"] == cid and row["Name"] == "/" + spec["name"]
        assert row["Image"] == spec["image"] and row["Config"]["Labels"] == spec["labels"]
        config, host = row["Config"], row["HostConfig"]
        assert config["User"] == spec["user"]
        assert config["Entrypoint"] == [spec["command"][0]]
        assert config["Cmd"] == list(spec["command"][1:])
        assert config["OpenStdin"] is spec["interactive"] and not config["Tty"]
        assert not config.get("ExposedPorts")
        assert host["ReadonlyRootfs"] and not host["Privileged"]
        assert host["CapDrop"] == ["ALL"] and not host.get("CapAdd")
        assert host["SecurityOpt"] == ["no-new-privileges"]
        assert host["Memory"] == 128 * 1024**2 and host["NanoCpus"] == 500_000_000
        assert host["PidsLimit"] == 32 and host["IpcMode"] == "private"
        assert host["RestartPolicy"] == {"Name": "no", "MaximumRetryCount": 0}
        assert host["NetworkMode"] == spec["network"] and row["RestartCount"] == 0
        assert not any(
            host.get(key)
            for key in (
                "Binds",
                "PortBindings",
                "PublishAllPorts",
                "ExtraHosts",
                "Links",
                "Devices",
                "DeviceRequests",
                "DeviceCgroupRules",
                "GroupAdd",
                "PidMode",
                "VolumesFrom",
                "Sysctls",
            )
        )
        assert (host.get("Tmpfs") or {}) == spec["tmpfs"]
        assert sorted((m["Name"], m["Destination"], m["RW"]) for m in row["Mounts"]) == sorted(
            spec["mounts"]
        )
        attached = row["NetworkSettings"]["Networks"]
        if spec["network"] == "none":
            assert set(attached) <= {"none"}
            assert all(
                not row.get("IPAddress") and not row.get("GlobalIPv6Address")
                for row in attached.values()
            )
        else:
            assert len(attached) == 1
            key = next(iter(attached))
            network = next(iter(attached.values()))
            assert key in {spec["network"], spec["network_name"]}
            assert network["NetworkID"] == spec["network"] or (
                network["NetworkID"] == ""
                and row["State"]["Status"] == "created"
                and row["State"]["Running"] is False
                and row["State"]["Pid"] == 0
            )
            assert network["IPAMConfig"]["IPv4Address"] == spec["address"]
            if row["State"]["Running"]:
                assert network["IPAddress"] == spec["address"]
        return row

    def auxiliary(
        self, role, image, command, *, edge=None, mounts=(), interactive=False, start=True
    ):
        assert role in {"db", "controller", "db-admin-0", "db-admin-1"}
        admin = role.startswith("db-admin-")
        assert (edge is None) is admin and (not admin or (interactive and not start))
        assert self.headroom() is True
        spec = dict(
            name=self.prefix + "-" + role,
            role=role,
            image=self.images[image],
            command=tuple(command),
            user="10002:10002" if role == "db" or admin else "10001:10001",
            network=self.plan.network(edge).identifier if edge else "none",
            network_name=self.prefix + "-" + edge if edge else "none",
            address=self.plan.address(edge, role) if edge else None,
            mounts=tuple(mounts),
            interactive=interactive,
            tmpfs={"/tmp": "rw,noexec,nosuid,size=2m,mode=1777"} if role == "controller" else {},
            labels={inv.LABEL: self.prefix, inv.LABEL + ".role": role},
        )
        fingerprint = sha256(inv.canonical(spec)).hexdigest()
        self.aux_journal.record(
            "reserve", kind="container", name=spec["name"], fingerprint=fingerprint
        )
        args = [
            "create",
            "--name",
            spec["name"],
            "--network",
            spec["network"],
            "--read-only",
            "--user",
            spec["user"],
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            str(128 * 1024**2),
            "--cpus",
            "0.5",
            "--pids-limit",
            "32",
            "--ipc",
            "private",
            "--restart",
            "no",
        ]
        if edge:
            args += ["--ip", spec["address"]]
        for key, value in spec["labels"].items():
            args += ["--label", key + "=" + value]
        for path, options in spec["tmpfs"].items():
            args += ["--tmpfs", path + ":" + options]
        for name, path, writable in mounts:
            args += [
                "--mount",
                f"type=volume,src={name},dst={path}" + ("" if writable else ",readonly"),
            ]
        if interactive:
            args += ["--interactive"]
        if role == "db":
            args += ["--stop-signal", "SIGINT"]
        args += ["--entrypoint", command[0], spec["image"], *command[1:]]
        assert not self.docker(
            "container",
            "ls",
            "-a",
            "--filter",
            "name=^" + spec["name"] + "$",
            "--format",
            "{{.ID}}",
        )
        cid = self.docker(*args)
        assert re.fullmatch("[0-9a-f]{64}", cid)
        self.auxiliaries.append((spec, cid, fingerprint))
        self.attest_auxiliary(spec, cid)
        self.aux_journal.record(
            "observe", kind="container", name=spec["name"], identity=cid, fingerprint=fingerprint
        )
        if start:
            assert self.docker("start", cid) == cid
            row = self.attest_auxiliary(spec, cid)
            assert row["State"]["Running"] and row["State"]["Pid"] > 0
        return cid

    def private(self, command, frame):
        task = owner_module("bounded_composition_actor").BoundedActor(
            (
                sys.executable,
                "-I",
                str(Path(engine_module.__file__).resolve()),
                "--private-command",
                self.binary,
                "--host",
                "unix:///var/run/docker.sock",
                "--config",
                str(self.config),
                *command,
            ),
            budget_ns=min(10_000_000_000, self.deadline - time.monotonic_ns() - 2_000_000_000),
            grace_ns=300_000_000,
        )
        result = task.execute(private_input=frame)
        assert set(result) == {"output"}
        return result["output"]

    def material_check(self, role, descriptor):
        assert descriptor == self.plan.descriptor(role)
        assert self.staged[role].verify(role, self.plan.fingerprint(role)) is True
        helper = self.material_helpers[role]
        # Fresh metadata for the exact successful install/read-back pair. The
        # exclusive runner creates no other writable material mounts; app mounts
        # are read-only. State is deliberately independent and mutable.
        for mode, cid in helper.owned.items():
            helper._check(self.row("container", cid), mode, exited=True)
        return True

    def start_services(self):
        address = self.plan.address("member-db", "db")
        settings = (
            "listen_addresses=" + address,
            "port=5432",
            "unix_socket_directories=",
            "hba_file=/database-material/pg_hba.conf",
            "ssl=on",
            "ssl_cert_file=/database-material/server.pem",
            "ssl_key_file=/database-material/server.key",
            "ssl_min_protocol_version=TLSv1.3",
            "password_encryption=scram-sha-256",
            "logging_collector=off",
            "log_statement=none",
            "log_min_error_statement=panic",
            "shared_buffers=16MB",
            "max_connections=10",
            "fsync=on",
            "synchronous_commit=on",
            "statement_timeout=3000",
            "idle_in_transaction_session_timeout=3000",
        )
        command = ["/usr/lib/postgresql/16/bin/postgres", "-D", "/database-data/pgdata"]
        for setting in settings:
            command += ["-c", setting]
        db = self.auxiliary(
            "db",
            "bootstrap",
            command,
            edge="member-db",
            mounts=(
                (self.plan.database_volume("material"), "/database-material", False),
                (self.plan.database_volume("data"), "/database-data", True),
            ),
        )
        client = self.auxiliary(
            "controller",
            "broker",
            (
                "/app/apps/api/.venv/bin/python",
                "/opt/ciq-composition/composition_client.py",
                "hold",
            ),
            edge="controller-broker",
        )
        launcher = Launcher(
            self.plan,
            engine=Unconfigured(),
            material_check=self.material_check,
            auxiliaries={"db": db, "controller": client},
            journal=self.journal,
            database=True,
        )
        self.launcher = launcher
        binding = Binding(
            "physical-" + uuid4().hex[:12], self.plan.generation, inventory(launcher.services)
        )
        commands = [
            *(("image", "inspect", image) for _, image in self.plan.images),
            *(("network", "inspect", n.identifier) for n in self.plan.networks),
            *(
                ("volume", "inspect", s["name"])
                for s in self.resources.specs
                if s["kind"] == "volume"
            ),
            ("inspect", "--format", "[{{json .}}]", "{incarnation}"),
            ("start", "{incarnation}"),
            ("stop", "--time", "30", "{incarnation}"),
        ]
        for role in inv.ROLES:
            commands.append(
                (
                    "container",
                    "ls",
                    "-a",
                    "--filter",
                    "name=^" + self.plan.name(role) + "$",
                    "--format",
                    "{{.ID}}",
                )
            )
            args = self.plan.create_arguments(role)
            commands.append(
                (
                    *args[:-1],
                    "--label",
                    f"{inv.LABEL}.attempt={binding.attempt}",
                    "--label",
                    f"{inv.LABEL}.fingerprint={binding.fingerprint}",
                    args[-1],
                )
            )
            for network, ip in self.plan.attachments(role)[1:]:
                commands.append(("network", "connect", "--ip", ip, network, "{incarnation}"))
        # The material callback also inspects acknowledged helper IDs, in a
        # separate owner read channel; app transport registers only eight CIDs.
        bounded = self.engine(tuple(commands))
        owner = self

        class AdmittedEngine:
            def __call__(self, *args):
                # Docker pretty-prints many per-edge runtime fields after start.
                # Compact the same complete object within the fixed actor frame;
                # do not drop any ownership, mount, state or network metadata.
                if args[:1] == ("inspect",):
                    args = ("inspect", "--format", "[{{json .}}]", args[-1])
                if args[:1] == ("create",):
                    try:
                        assert owner.headroom() is True
                    except Exception:
                        bounded.fenced = True
                        raise
                return bounded(*args)

            def permit_incarnation(self, cid):
                bounded.permit_incarnation(cid)

        launcher.engine = AdmittedEngine()
        approval = FixtureApproval()
        approval.pending.add(binding)
        domain = "physical-test-monotonic"
        controller = Controller(
            launcher,
            limits=Limits(180_000_000_000, 30_000_000_000, 30_000_000_000, 300_000_000_000, 1, 128),
            domain=domain,
            approval=approval,
            clock=lambda: Sample(domain, time.monotonic_ns()),
            cancel=lambda *_: self.stop_auxiliary(client),
        )
        self.controller = controller
        try:
            assert controller.start(binding.attempt) == binding
        except Exception as failure:
            print("Physical launch denied at closed stage: " + repr(launcher.stage), flush=True)
            print("Acknowledged application roles: " + repr(sorted(launcher.owned)), flush=True)
            seen = set()
            cause = failure
            while cause is not None and id(cause) not in seen:
                seen.add(id(cause))
                for frame in traceback.extract_tb(cause.__traceback__):
                    if Path(frame.filename).name in {
                        "composition_inventory.py",
                        "composition_launcher.py",
                    }:
                        print(
                            f"Owned validation location: {Path(frame.filename).name}:"
                            f"{frame.lineno} {frame.name}",
                            flush=True,
                        )
                cause = cause.__context__
            for role, cid in launcher.owned.items():
                state = self.row("container", cid)["State"]
                print(
                    "Owned runtime state: "
                    + json.dumps(
                        {
                            "role": role,
                            "running": state["Running"],
                            "exit": state["ExitCode"],
                            "oom": state["OOMKilled"],
                        }
                    ),
                    flush=True,
                )
            raise
        assert controller.supervisor.state is State.STARTING and len(launcher.owned) == 8
        self.client = client
        print(
            "Physical application launch: all eight exact service incarnations running", flush=True
        )

    def probe(self, pki, profile, tenant, request_id, *, token=None):
        settings = SimpleNamespace(
            auth_mode="local",
            environment="test",
            oidc_audience="cashlessiq-api",
            local_auth_secret=SecretStr("fictional-composition-local-auth-secret"),
        )
        token = (
            token
            if token is not None
            else issue_local_token(settings, profile.subject, tenant.tenant_id)
        )
        frame = inv.canonical(
            dict(
                address=self.plan.address("controller-broker", "broker"),
                pin=dict(self.plan.pins)["broker"],
                ca=pki[0].read_text(),
                certificate=pki[1]["controller"][0].read_text(),
                private_key=pki[1]["controller"][1].read_text(),
                token=token,
                request_id=request_id,
            )
        )
        result = self.private(
            (
                "exec",
                "--interactive",
                self.client,
                "/app/apps/api/.venv/bin/python",
                "/opt/ciq-composition/composition_client.py",
                "summary",
            ),
            frame,
        )
        value = json.loads(result)
        assert type(value) is dict and value.get("state") in {"VERIFIED", "DENIED"}
        return value

    def accept_requests(self, pki):
        c = self.controller
        checked = 0
        for index, tenant in enumerate(SOURCE_TENANTS):
            request_id = "GOL001" if index == 0 else "GOL024"
            foreign_id = "GOL024" if index == 0 else "GOL001"
            for profile in tenant.profiles:
                end = min(self.deadline, time.monotonic_ns() + 30_000_000_000)
                while True:
                    value = self.probe(pki, profile, tenant, request_id)
                    if value["state"] == "VERIFIED" or time.monotonic_ns() >= end:
                        break
                    # Retry only a closed readiness read, never allocation or
                    # initialization. No self-test result is delivered to users.
                    time.sleep(0.2)
                assert value["state"] == "VERIFIED", "Functional private-chain readiness failed"
                summary = SummaryObservation.model_validate(value["summary"])
                assert summary.tpa_id == tenant.tpa_id and summary.request_id == request_id
                if index == 0:
                    assert (
                        summary.recommendation.state == "SAVED"
                        and summary.recommendation.payable_inr == 95000
                    )
                else:
                    assert summary.recommendation.state == "MISSING"
                assert self.probe(pki, profile, tenant, foreign_id) == {"state": "DENIED"}
                checked += 1
        self.accept_revocation(pki)
        # These are closed synthetic readiness self-tests, not user delivery.
        # Every reader/validator route and the real membership DB was exercised.
        for service in self.launcher.services:
            with pytest.raises(SupervisorDenied):
                c.admit("GOL001")
            c.acknowledge(Ready(c.supervisor.binding, service, self.launcher.owned[service.role]))
        assert c.supervisor.state is State.READY
        for index, tenant in enumerate(SOURCE_TENANTS):
            for profile in tenant.profiles:
                request_id = "GOL001" if index == 0 else "GOL027"
                operation = c.admit(request_id)
                value = self.probe(pki, profile, tenant, request_id)
                assert value["state"] == "VERIFIED"
                summary = SummaryObservation.model_validate(value["summary"])
                assert c.complete(operation, summary) == summary
        assert c.supervisor.active_count == 0
        assert c.stop() is True and c.supervisor.state is State.STOPPED
        assert len(self.launcher._stopped) == 8
        for cid in self.launcher.owned.values():
            state = self.row("container", cid)["State"]
            assert state["ExitCode"] == 0 and not state["OOMKilled"] and not state["Error"]
        print(
            f"Physical readiness/delivery: {checked} tenant-role routes, "
            "six foreign-case denials, six supervised results, all-eight stop",
            flush=True,
        )

    def accept_revocation(self, pki):
        # Closed startup self-tests only. Stop and prove DB exit before each
        # single-user maintenance operation; no extra SQL grant or Unix socket.
        # The eight app incarnations stay running, so membership cannot be cached.
        db = self.launcher.auxiliaries["db"]
        original = {
            role: self.row("container", cid)["State"]["StartedAt"]
            for role, cid in self.launcher.owned.items()
        }
        tenant = SOURCE_TENANTS[0]
        processor, medical = tenant.profiles[:2]
        for index, active in enumerate((False, True)):
            assert self.stop_auxiliary(db) is True
            assert self.row("container", db)["State"]["ExitCode"] == 0
            assert self.probe(pki, medical, tenant, "GOL001") == {"state": "DENIED"}
            helper = self.auxiliary(
                f"db-admin-{index}",
                "bootstrap",
                (
                    "/usr/lib/postgresql/16/bin/postgres",
                    "--single",
                    "-D",
                    "/database-data/pgdata",
                    "-c",
                    "shared_buffers=16MB",
                    "-c",
                    "max_connections=10",
                    "synthetic",
                ),
                mounts=((self.plan.database_volume("data"), "/database-data", True),),
                interactive=True,
                start=False,
            )
            sql = (
                f"UPDATE ops.tenant_membership SET active={'true' if active else 'false'} "
                f"WHERE user_id='{processor.user_id}' AND tenant_id='{tenant.tenant_id}';\n"
            ).encode()
            self.private(("start", "--attach", "--interactive", helper), sql)
            state = self.row("container", helper)["State"]
            assert state["Running"] is False and state["Pid"] == 0
            assert state["ExitCode"] == 0 and not state["OOMKilled"] and not state["Error"]
            assert self.docker("start", db) == db
            end = min(self.deadline, time.monotonic_ns() + 15_000_000_000)
            while True:
                value = self.probe(pki, medical, tenant, "GOL001")
                if value["state"] == "VERIFIED" or time.monotonic_ns() >= end:
                    break
                time.sleep(0.2)
            assert value["state"] == "VERIFIED", "DB restore did not restore a fresh valid role"
            value = self.probe(pki, processor, tenant, "GOL001")
            assert value["state"] == ("VERIFIED" if active else "DENIED")
        for role, cid in self.launcher.owned.items():
            row = self.row("container", cid)
            assert row["State"]["Running"] and row["State"]["StartedAt"] == original[role]
        print(
            "Physical fresh membership: revocation/restore and two DB outage denials; "
            "app incarnations unchanged",
            flush=True,
        )

    def stop_auxiliary(self, cid):
        try:
            spec, _, _ = next(row for row in self.auxiliaries if row[1] == cid)
            row = self.attest_auxiliary(spec, cid)
            if row["State"]["Running"]:
                assert self.docker("stop", "--time", "5", cid) == cid
            row = self.attest_auxiliary(spec, cid)
            return (
                row["State"]["Running"] is False
                and row["State"]["Pid"] == 0
                and row["State"]["Status"] in {"created", "exited"}
                and not any(row["State"].get(key) for key in ("Paused", "Restarting", "Dead"))
            )
        except Exception:
            return False

    def close(self):
        # Only known full IDs with a fresh exact helper check qualify for removal.
        clean = True
        if self.controller is not None:
            try:
                assert self.controller.stop() is True
                for role, cid in self.launcher.owned.items():
                    row = self.row("container", cid)
                    assert self.launcher._identity(role, row) == cid
                    assert row["State"]["Running"] is False and row["State"]["Pid"] == 0
                    assert self.docker("container", "rm", cid) == cid
                    self.journal.record(
                        "removed",
                        kind="container",
                        name=self.plan.name(role),
                        identity=cid,
                        fingerprint=self.plan.fingerprint(role),
                    )
            except Exception:
                clean = False
        if not ledger.fold(self.aux_journal.events)[2]:
            self.aux_journal.fence()
        for spec, cid, fingerprint in reversed(self.auxiliaries):
            try:
                assert self.stop_auxiliary(cid) is True
                self.aux_journal.record(
                    "stopped",
                    kind="container",
                    name=spec["name"],
                    identity=cid,
                    fingerprint=fingerprint,
                )
                assert self.docker("container", "rm", cid) == cid
                self.aux_journal.record(
                    "removed",
                    kind="container",
                    name=spec["name"],
                    identity=cid,
                    fingerprint=fingerprint,
                )
            except Exception:
                clean = False
        self.aux_journal.close()
        for helper in reversed(self.helpers):
            try:
                assert helper.contain() is True
                for mode, cid in helper.owned.items():
                    row = self.row("container", cid)
                    helper._check(row, mode, configuration_only=True)
                    assert row["State"]["Running"] is False and row["State"]["Pid"] == 0
                    assert row["State"]["Status"] == "exited"
                    assert self.docker("container", "rm", cid) == cid
                    helper.journal.record(
                        "removed",
                        kind="container",
                        name=helper.name(mode),
                        identity=cid,
                        fingerprint=helper.fingerprint(mode),
                    )
            except Exception:
                clean = False
            finally:
                helper.journal.close()
        if not ledger.fold(self.journal.events)[2]:
            self.journal.fence()
        for spec in reversed(self.resources.specs):
            identity = self.resources.observed.get(spec["name"])
            if identity is None:
                if spec["name"] in self.resources.attempted:
                    clean = False  # UNKNOWN is never absence or a cleanup target.
                continue
            try:
                row = self.row(spec["kind"], identity)
                assert row["Name"] == spec["name"] and row["Labels"] == spec["labels"]
                if spec["kind"] == "network":
                    assert row["Id"] == identity and not row["Containers"]
                    assert row["Driver"] == "bridge" and row["Internal"] is True
                else:
                    assert row["Driver"] == row["Scope"] == "local" and not row.get("Options")
                assert self.docker(spec["kind"], "rm", identity) == identity
                names = self.docker(spec["kind"], "ls", "--format", "{{.Name}}").splitlines()
                assert spec["name"] not in names
                self.journal.record(
                    "removed",
                    kind=spec["kind"],
                    name=spec["name"],
                    identity=identity,
                    fingerprint=sha256(inv.canonical(spec)).hexdigest(),
                )
            except Exception:
                clean = False
        self.journal.close()
        assert clean, "Uncertain resources retained for disposable runner teardown"


def test_real_disposable_eight_service_chain(tmp_path, assertion_key):
    pki = create_pki(tmp_path / "pki")
    owner = PhysicalOwner(tmp_path, pki)
    try:
        owner.allocate()
        owner.prepare(pki, assertion_key)
        owner.start_services()
        owner.accept_requests(pki)
        assert owner.headroom.samples >= 36
        print("Physical acceptance: 35 resources, 19 helper pairs and eight-service chain verified")
    finally:
        owner.close()
    recovered = ledger.inspect(owner.journal.root)
    assert recovered.fenced and len(recovered.resources) == 43
    assert {row[-1] for row in recovered.resources} == {"REMOVED"}
