"""CI-only TLS acceptance on a fresh internal bridge; not the full allocator.

Docker assigns a free subnet. Its actual ID/subnet are injected into the member
edge before generating the HBA/PKI. No host ports or external network attachment.
The disposable runner owns final cleanup; this is not operational recovery.
"""

import json
import os
import re
from dataclasses import replace
from ipaddress import IPv4Network
from pathlib import Path

import pytest

if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CIQ_DATABASE_IMAGE_TEST") != "1":
    pytest.skip("Dedicated disposable CI image job required", allow_module_level=True)

from scripts.composition_database import prepare
from scripts.disposable_membership_db import SOURCE_PROFILES
from tests.integration.test_composition_database_images import (
    DATA,
    LABEL,
    MATERIAL,
    DatabaseImages,
    PrivateFrame,
    bootstrap_database,
    docker,
    inspect,
)
from tests.test_composition_database import plan


class NetworkedDatabaseImages(DatabaseImages):
    def __init__(self):
        super().__init__()
        self.network = None
        image = (Path(os.environ["RUNNER_TEMP"]) / "membership-image-id").read_text().strip()
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", image)
        row = inspect("image", image)
        assert row["Id"] == image and row["Config"]["User"] == "10001:10001"
        assert not row["Config"].get("Volumes") and not row["Config"].get("ExposedPorts")
        self.images["membership"] = image

    def edge(self):
        name = f"ciq-db-image-{self.token}-member-db"
        absent = docker("network", "inspect", name)
        assert absent.returncode == 1 and b"not found" in absent.stderr.lower()
        result = docker(
            "network",
            "create",
            "--driver",
            "bridge",
            "--internal",
            "--label",
            f"{LABEL}={self.token}",
            name,
        )
        assert result.returncode == 0, "Fresh internal CI bridge creation failed; do not retry"
        network = result.stdout.strip().decode()
        assert re.fullmatch("[0-9a-f]{64}", network)
        self.network = network
        row = inspect("network", network)
        assert row["Id"] == network and row["Name"] == name
        assert row["Labels"][LABEL] == self.token
        assert row["Driver"] == "bridge" and row["Internal"] is True
        assert not row["Options"] and not row["Containers"] and not row["EnableIPv6"]
        assert row["IPAM"]["Driver"] == "default" and len(row["IPAM"]["Config"]) == 1
        spec = row["IPAM"]["Config"][0]
        subnet = IPv4Network(spec["Subnet"], strict=True)
        assert spec["Gateway"] == str(subnet.network_address + 1)
        original = plan()
        # Inventory validates private range/prefix and all subnet overlaps.
        return replace(
            original,
            networks=tuple(
                replace(n, identifier=network, subnet=str(subnet)) if n.edge == "member-db" else n
                for n in original.networks
            ),
        )

    def container(self, image, command, mounts, address, *, interactive=False):
        user = "10001:10001" if image == "membership" else "10002:10002"
        name = f"ciq-db-image-{self.token}-{len(self.containers)}"
        args = [
            "container",
            "create",
            "--name",
            name,
            "--label",
            f"{LABEL}={self.token}",
            "--network",
            self.network,
            "--ip",
            address,
            "--read-only",
            "--user",
            user,
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "128m",
            "--cpus",
            "0.5",
            "--pids-limit",
            "32",
            "--ipc",
            "private",
            "--restart",
            "no",
            "--entrypoint",
            command[0],
        ]
        if interactive:
            args += [
                "--interactive",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=1m,mode=0700,uid=10001,gid=10001",
            ]
        for volume, destination, writable in mounts:
            mount = f"type=volume,src={volume},dst={destination},volume-nocopy"
            args += ["--mount", mount + ("" if writable else ",readonly")]
        result = docker(*args, self.images[image], *command[1:])
        assert result.returncode == 0, "Networked CI container creation failed; do not retry"
        cid = result.stdout.strip().decode()
        assert re.fullmatch("[0-9a-f]{64}", cid)
        self.containers.append(cid)
        row = inspect("container", cid)
        assert row["Id"] == cid and row["Image"] == self.images[image]
        assert row["Config"]["Labels"][LABEL] == self.token and row["Config"]["User"] == user
        assert row["Config"]["Entrypoint"] == [command[0]]
        assert row["Config"]["Cmd"] == list(command[1:])
        assert not row["Config"].get("ExposedPorts") and not row["Config"]["Tty"]
        assert row["Config"]["OpenStdin"] is interactive
        host = row["HostConfig"]
        assert host["NetworkMode"] == self.network and host["ReadonlyRootfs"]
        assert host["CapDrop"] == ["ALL"] and not host.get("CapAdd")
        assert host["SecurityOpt"] == ["no-new-privileges"]
        assert (host["Memory"], host["NanoCpus"], host["PidsLimit"]) == (
            128 * 1024**2,
            500_000_000,
            32,
        )
        assert host["RestartPolicy"] == {"Name": "no", "MaximumRetryCount": 0}
        assert host["IpcMode"] == "private" and not host["Privileged"]
        assert not any(
            host.get(k)
            for k in (
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
            )
        )
        assert (host.get("Tmpfs") or {}) == (
            {"/tmp": "rw,noexec,nosuid,size=1m,mode=0700,uid=10001,gid=10001"}
            if interactive
            else {}
        )
        assert sorted((m["Name"], m["Destination"], m["RW"]) for m in row["Mounts"]) == sorted(
            mounts
        )
        attached = list(row["NetworkSettings"]["Networks"].values())
        assert len(attached) == 1 and attached[0]["IPAMConfig"]["IPv4Address"] == address
        assert row["State"]["Status"] == "created" and not row["State"]["Running"]
        return cid

    def running(self, cid, address):
        row = inspect("container", cid)
        assert row["State"]["Running"] and not row["State"]["OOMKilled"]
        attached = list(row["NetworkSettings"]["Networks"].values())
        assert len(attached) == 1
        assert (attached[0]["NetworkID"], attached[0]["IPAddress"]) == (self.network, address)
        endpoints = inspect("network", self.network)["Containers"]
        assert set(endpoints) <= set(self.containers)

    def client(self, body, address, action, expected):
        cid = self.container(
            "membership",
            ("python", "-m", "ciq_membership_runtime.composition_db_probe", action),
            [],
            address,
            interactive=True,
        )
        result = docker(
            "container",
            "start",
            "--attach",
            "--interactive",
            cid,
            frame=body,
            timeout=60,
        )
        state = inspect("container", cid)["State"]
        assert not state["Running"] and not state["OOMKilled"] and not state["Error"]
        assert state["ExitCode"] == result.returncode == 0, "Membership TLS acceptance failed"
        assert result.stderr == b"" and json.loads(result.stdout) == expected

    def close(self):
        super().close()
        if self.network:
            row = inspect("network", self.network)
            assert row["Labels"][LABEL] == self.token and not row["Containers"]
            assert docker("network", "rm", self.network).returncode == 0


@pytest.fixture
def networked_images():
    owner = NetworkedDatabaseImages()
    try:
        yield owner
    finally:
        owner.close()


def test_fresh_membership_tls_registry_denials_and_clean_stop(networked_images, tmp_path):
    owner = networked_images
    inventory = owner.edge()
    bundle = prepare(inventory)
    frame, material, data = bootstrap_database(owner, tmp_path, bundle)
    mounts = [(material, MATERIAL, False), (data, DATA, True)]
    owner.run(
        "bootstrap",
        "composition_database_bootstrap",
        "verify",
        frame,
        [(material, MATERIAL, False), (data, DATA, False)],
    )
    address = inventory.address("member-db", "db")
    # Closed test-only command, direct postgres PID 1, no server secrets in argv.
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
    server = owner.container("bootstrap", command, mounts, address)
    assert docker("container", "start", server).returncode == 0
    owner.running(server, address)
    body = PrivateFrame(
        json.dumps(
            dict(
                config=json.loads(bundle.membership["db.json"]),
                ca=bundle.membership["db-ca.pem"].decode(),
                wrong_ca=prepare(inventory).membership["db-ca.pem"].decode(),
                profiles=SOURCE_PROFILES,
            )
        ).encode()
    )
    owner.client(
        body,
        inventory.address("member-db", "membership"),
        "membership",
        dict(
            state="VERIFIED",
            profiles=6,
            cross_tenant_absences=6,
            privilege_denials=9,
            connection_denials=7,
        ),
    )
    owner.running(server, address)
    unauthorized = str(IPv4Network(inventory.network("member-db").subnet).network_address + 4)
    owner.client(body, unauthorized, "source-denied", dict(state="VERIFIED", source_denials=1))
    owner.running(server, address)
    assert (
        docker("container", "stop", "--signal", "SIGINT", "--timeout", "5", server).returncode == 0
    )
    state = inspect("container", server)["State"]
    assert not state["Running"] and not state["OOMKilled"] and state["Error"] == ""
    assert state["ExitCode"] == 0, "Fast shutdown must complete without forced kill"
    # Fresh read-only helper proves marker retention and no postmaster.pid.
    owner.run(
        "bootstrap",
        "composition_database_bootstrap",
        "verify",
        frame,
        [(material, MATERIAL, False), (data, DATA, False)],
    )
