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
from hashlib import sha256
from ipaddress import IPv4Network
from pathlib import Path
from uuid import uuid4

import pytest

if (
    sys.platform != "linux"
    or os.environ.get("GITHUB_ACTIONS") != "true"
    or os.environ.get("CIQ_COMPOSITION_TEST") != "1"
):
    pytest.skip("Dedicated disposable Linux composition job required", allow_module_level=True)

from composition_inventory_fixture import implementation as inv
from composition_journal_fixture import implementation as ledger
from composition_material_fixture import TLS_NAMES, bundles
from test_worker_guard_mtls import assertion_key as assertion_key
from test_worker_transport import pki as pki


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
        subnets = tuple(IPv4Network("172.30.252.0/24").subnets(new_prefix=29))[:18]
        headroom_engine = self.engine(headroom_module.COMMANDS, budget_ns=5_000_000_000)
        self.headroom = headroom_module.LinuxHeadroom(headroom_engine, self.deadline, root)
        collision = routes.CollisionCheck(
            self.engine(routes.COMMANDS), self.deadline, route_reader=routes.linux_host_routes
        )
        self.resources = resources_module.Resources(
            prefix=self.prefix,
            images=tuple((kind, self.images[kind]) for kind in ("worker", "membership", "broker")),
            pins=tuple((role, pki[1][name][2]) for role, name in TLS_NAMES.items()),
            subnets={edge: str(subnet) for edge, subnet in zip(inv.EDGES, subnets, strict=True)},
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
        for role, (spec, data) in generated.items():
            staged = spec.provision(staging, data)
            self.helper("composition_helpers", "Helpers", "material", staged)
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

    def close(self):
        # Only known full IDs with a fresh exact helper check qualify for removal.
        clean = True
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


def test_real_allocator_and_all_private_helper_handoffs(tmp_path, pki, assertion_key):
    owner = PhysicalOwner(tmp_path, pki)
    try:
        owner.allocate()
        owner.prepare(pki, assertion_key)
        assert owner.headroom.samples >= 36
        print("Physical acceptance: 18 networks, 17 volumes, 19 helper pairs verified")
    finally:
        owner.close()
    recovered = ledger.inspect(owner.journal.root)
    assert recovered.fenced and len(recovered.resources) == 35
    assert {row[-1] for row in recovered.resources} == {"REMOVED"}
