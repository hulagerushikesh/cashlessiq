"""Disposable mTLS/delegation smoke; no real auth/source/deployment.

Run: uv run --project apps/worker --frozen python scripts/test_worker_mtls.py
Optional --restricted-db adds a fifth, ephemeral PostgreSQL container.
Only invocation-owned Docker resources are removed; normal product stack is untouched.
"""

import argparse
import ipaddress
import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from disposable_membership_db import DisposableMembershipDB

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("broker", "reader", "validator", "membership")
EDGES = (
    ("broker", "reader"),
    ("reader", "validator"),
    ("reader", "membership"),
    ("validator", "membership"),
)
AUDIENCES = {
    "broker": "broker",
    "reader": "reader:0:nonclinical",
    "validator": "validator:0",
    "membership": "membership:0",
}


def docker(*arguments, capture=True, timeout=60, input=None):
    result = subprocess.run(
        ["docker", *arguments],
        cwd=ROOT,
        text=True,
        input=input,
        check=True,
        timeout=timeout,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if input is not None else None,
    )
    return result.stdout.strip() if capture else None


def write(path, data):
    # Temporary test artifacts only; parent temporary directory remains mode 0700.
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    path.chmod(0o444)


def private_bytes(key):
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def fixture():
    case = dict(
        request_id="GOL001",
        policy_id="POL0001",
        tpa_id="TPA001",
        product_id="AS_NIA_V02_2425",
        product_name="Synthetic test product",
        policy_version="TEST",
        continuous_cover_since="2023-01-01",
        admission_date="2026-10-02",
        estimated_total_inr=100_000,
    )
    decision = dict(
        request_id="GOL001",
        outcome="APPROVE_WITH_DEDUCTIONS",
        total_claimed_inr=100_000,
        total_payable_inr=95_000,
        lines=[
            dict(
                item="Synthetic test item",
                claimed_inr=100_000,
                payable_inr=95_000,
                deduction_inr=5_000,
                reason="Restricted synthetic prose",
                calc="Saved trace",
                citations=[{"type": "clause", "id": "COPAY"}],
            )
        ],
        queries=[],
        refer_reasons=[],
        summary="Restricted synthetic narrative",
        sla={"elapsed_min": 0, "state": "GREEN"},
    )
    return dict(
        case=case,
        decisions=[
            dict(
                request_id="GOL001",
                tpa_id="TPA001",
                outcome=decision["outcome"],
                payable_inr=95_000,
                decision_json=decision,
            )
        ],
        evidence=[
            dict(
                request_id="GOL001",
                tpa_id="TPA001",
                product_id="AS_NIA_V02_2425",
                clause_id="COPAY",
                heading="Synthetic co-pay",
                page=5,
                source_url="https://example.com/policy.pdf",
            )
        ],
    )


def main(
    *, retained_replay=False, restricted_db=False, verified_db_tls=False, signing_generation=False
):
    assert not signing_generation or (retained_replay and verified_db_tls)
    restricted_db = restricted_db or verified_db_tls
    prefix = f"ciq-mtls-{uuid4().hex[:12]}"
    image = f"{prefix}:test"
    membership_image = f"{prefix}:membership"
    containers, networks, volumes = {}, [], {}
    try:
        docker(
            "build",
            "--target",
            "mtls-test",
            "-f",
            "apps/worker/Dockerfile",
            "-t",
            image,
            ".",
            capture=False,
            timeout=300,
        )
        if restricted_db:
            docker(
                "build",
                "--target",
                "mtls-test",
                "-f",
                "apps/membership/Dockerfile",
                "-t",
                membership_image,
                ".",
                capture=False,
                timeout=300,
            )
        if retained_replay:
            for role in ("reader", "validator"):
                volume = docker(
                    "volume",
                    "create",
                    "--label",
                    f"cashlessiq.mtls-test={prefix}",
                    f"{prefix}-{role}-replay",
                )
                volumes[role] = volume
                docker(
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--read-only",
                    "--user",
                    "0:0",
                    "--cap-drop",
                    "ALL",
                    "--cap-add",
                    "CHOWN",
                    "--security-opt",
                    "no-new-privileges",
                    "--mount",
                    f"type=volume,src={volume},dst=/var/lib/ciq-replay",
                    image,
                    "initialize-replay",
                    role,
                )
        links = {role: {} for role in ROLES}
        for left, right in EDGES:
            network = docker(
                "network",
                "create",
                "--internal",
                "--label",
                f"cashlessiq.mtls-test={prefix}",
                f"{prefix}-{left}-{right}",
            )
            networks.append(network)
            links[left][right] = network
            links[right][left] = network
        with TemporaryDirectory(prefix="ciq-disposable-pki-") as directory:
            root = Path(directory)
            database = None
            if restricted_db:
                network = docker(
                    "network",
                    "create",
                    "--internal",
                    "--label",
                    f"cashlessiq.mtls-test={prefix}",
                    f"{prefix}-membership-db",
                )
                networks.append(network)
                links["membership"]["db"] = network
                # Register exact name BEFORE startup so partial failures are cleaned.
                containers["db"] = f"{prefix}-db"
                database = DisposableMembershipDB(
                    docker,
                    name=containers["db"],
                    network=network,
                    label=f"cashlessiq.mtls-test={prefix}",
                    directory=root,
                    verified_tls=verified_db_tls,
                )
                database.start()
            for role in ROLES:
                mount = root / role
                mount.mkdir(mode=0o755)
                args = [
                    "create",
                    "--name",
                    f"{prefix}-{role}",
                    "--network",
                    next(iter(links[role].values())),
                    "--label",
                    f"cashlessiq.mtls-test={prefix}",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--user",
                    "10001:10001",
                    "--memory",
                    "128m",
                    "--cpus",
                    "0.5",
                    "--pids-limit",
                    "32",
                    "--tmpfs",
                    "/tmp:rw,noexec,nosuid,size=8m,mode=1777",
                    "--mount",
                    f"type=bind,src={mount},dst=/run/ciq,readonly",
                ]
                if role in volumes:
                    args += ["--mount", f"type=volume,src={volumes[role]},dst=/var/lib/ciq-replay"]
                role_image = membership_image if restricted_db and role == "membership" else image
                args += ["--entrypoint", "python", role_image, "-c", "import time; time.sleep(300)"]
                containers[role] = docker(*args)
                for network in list(links[role].values())[1:]:
                    docker("network", "connect", network, containers[role])
                docker("start", containers[role])

            # Bootstrap sleeps reserve actual engine addresses; no listener exists yet.
            inspected = {role: json.loads(docker("inspect", containers[role]))[0] for role in ROLES}
            if signing_generation:
                # Simultaneously stopping two dynamic endpoints can swap their
                # leases on start. Reserve the observed addresses explicitly
                # before generating pinned certificates or starting listeners.
                for role in ("reader", "validator"):
                    for network, endpoint in inspected[role]["NetworkSettings"]["Networks"].items():
                        docker("network", "disconnect", network, containers[role])
                        docker(
                            "network",
                            "connect",
                            "--ip",
                            endpoint["IPAddress"],
                            network,
                            containers[role],
                        )
                    inspected[role] = json.loads(docker("inspect", containers[role]))[0]
            for role, config in inspected.items():
                host = config["HostConfig"]
                assert host["ReadonlyRootfs"] and host["CapDrop"] == ["ALL"]
                assert "no-new-privileges" in host["SecurityOpt"]
                assert config["Config"]["User"] == "10001:10001"
                assert not host["PortBindings"] and not config["Config"].get("ExposedPorts")
                assert {
                    net["NetworkID"] for net in config["NetworkSettings"]["Networks"].values()
                } == set(links[role].values())
                binds = [mount for mount in config["Mounts"] if mount["Type"] == "bind"]
                assert len(binds) == 1 and binds[0]["Source"] == str(root / role)
                assert binds[0]["Destination"] == "/run/ciq" and not binds[0]["RW"]
                replay_mounts = [mount for mount in config["Mounts"] if mount["Type"] == "volume"]
                assert len(replay_mounts) == (1 if role in volumes else 0)
                if role in volumes:
                    assert replay_mounts[0]["Name"] == volumes[role]
                    assert replay_mounts[0]["Destination"] == "/var/lib/ciq-replay"
                    assert replay_mounts[0]["RW"]
            assert all(
                json.loads(docker("network", "inspect", net))[0]["Internal"] for net in networks
            )

            def address(role, peer):
                network_id = links[role][peer]
                return next(
                    net["IPAddress"]
                    for net in inspected[role]["NetworkSettings"]["Networks"].values()
                    if net["NetworkID"] == network_id
                )

            ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            signer = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            now = datetime.now(UTC)
            ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Disposable CIQ CA")])
            ca = (
                x509.CertificateBuilder()
                .subject_name(ca_name)
                .issuer_name(ca_name)
                .public_key(ca_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=1))
                .not_valid_after(now + timedelta(hours=1))
                .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .add_extension(
                    x509.KeyUsage(False, False, False, False, False, True, True, False, False),
                    critical=True,
                )
                .sign(ca_key, hashes.SHA256())
            )
            pins = {}
            for role in ROLES:
                mount = root / role
                key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                ips = [address(role, peer) for peer in links[role]]
                leaf = (
                    x509.CertificateBuilder()
                    .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, role)]))
                    .issuer_name(ca_name)
                    .public_key(key.public_key())
                    .serial_number(x509.random_serial_number())
                    .not_valid_before(now - timedelta(minutes=1))
                    .not_valid_after(now + timedelta(hours=1))
                    .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
                    .add_extension(
                        x509.ExtendedKeyUsage(
                            [ExtendedKeyUsageOID.CLIENT_AUTH, ExtendedKeyUsageOID.SERVER_AUTH]
                        ),
                        True,
                    )
                    .add_extension(
                        x509.SubjectAlternativeName(
                            [
                                x509.UniformResourceIdentifier(
                                    f"urn:cashlessiq:worker:{AUDIENCES[role]}"
                                ),
                                *[x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips],
                            ]
                        ),
                        False,
                    )
                    .sign(ca_key, hashes.SHA256())
                )
                pins[role] = leaf.fingerprint(hashes.SHA256()).hex()
                write(mount / "ca.pem", ca.public_bytes(serialization.Encoding.PEM))
                write(mount / "identity.pem", leaf.public_bytes(serialization.Encoding.PEM))
                write(mount / "identity.key", private_bytes(key))
                write(
                    mount / "verify.pem",
                    signer.public_key().public_bytes(
                        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
                    ),
                )
            write(root / "broker" / "signing.key", private_bytes(signer))
            write(root / "validator" / "fixture.json", json.dumps(fixture()))
            state_path = root / "membership" / "state.json"
            if database:
                database.write_credential(root / "membership" / "db.json")
                for role in ("broker", "reader", "validator"):
                    docker(
                        "exec",
                        containers[role],
                        "python",
                        "-c",
                        "import socket,importlib.util; from pathlib import Path; "
                        "assert not Path('/run/ciq/db.json').exists(); "
                        "assert all(importlib.util.find_spec(x) is None for x in "
                        "('sqlalchemy','psycopg','ciq_api.worker_membership_store')); "
                        "s=socket.socket(); s.settimeout(1); "
                        f"assert s.connect_ex(({database.address!r},5432)) != 0; s.close()",
                    )
                print("PASS: only membership has DB credential/driver/network; workers denied")
            else:
                write(state_path, json.dumps({"role": "processor"}))
            for role in ROLES:
                targets = {peer: address(peer, role) for peer in links[role] if peer != "db"}
                if role == "broker":  # Negative direct-hop test: no broker/validator network.
                    targets["validator"] = address("validator", "reader")
                # Reader only listens on broker edge; outbound targets are independently fixed.
                listen = (
                    [address(role, peer) for peer in links[role] if peer != "db"]
                    if role == "membership"
                    else [address(role, "broker" if role == "reader" else "reader")]
                    if role != "broker"
                    else []
                )
                write(
                    root / role / "config.json",
                    json.dumps(
                        {
                            "pins": pins,
                            "targets": targets,
                            "listen": listen,
                            "retained_replay": retained_replay and role in volumes,
                            "restricted_db": restricted_db,
                            "verified_db_tls": verified_db_tls,
                        }
                    ),
                )
                if role != "broker":
                    docker(
                        "exec",
                        "-d",
                        containers[role],
                        "python",
                        "-m",
                        "ciq_worker_runtime.mtls_probe",
                        "serve",
                        role,
                    )

            def ready(role):
                deadline = time.monotonic() + 15
                while (
                    docker(
                        "exec",
                        containers[role],
                        "python",
                        "-c",
                        "from pathlib import Path; print(Path('/tmp/ready').exists())",
                    )
                    != "True"
                ):
                    if time.monotonic() > deadline:
                        raise RuntimeError(f"Test listener readiness failed: {role}")
                    time.sleep(0.1)

            for role in ("membership", "validator", "reader"):
                ready(role)

            def check(action):
                docker(
                    "exec",
                    containers["broker"],
                    "python",
                    "-m",
                    "ciq_worker_runtime.mtls_probe",
                    action,
                    "broker",
                    capture=False,
                )

            if signing_generation:
                check("fresh")  # Establish working old trust before negative acceptance.
                check("prepare-generation")

                def replay_digest(role):
                    return docker(
                        "exec",
                        containers[role],
                        "python",
                        "-m",
                        "ciq_worker_runtime.mtls_probe",
                        "replay-digest",
                        role,
                    )

                digests = {role: replay_digest(role) for role in ("reader", "validator")}
                # Broker is an idle test container, not a serving issuer. The
                # sequencer issues nothing until both authorities are restarted.
                # Stop both before changing their mounted verification material.
                for role in ("reader", "validator"):
                    docker("stop", "--time", "1", containers[role])
                assert all(
                    not json.loads(docker("inspect", containers[role]))[0]["State"]["Running"]
                    for role in ("reader", "validator")
                )
                replacement = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                public = replacement.public_key().public_bytes(
                    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
                )
                for role in ("broker", "reader", "validator"):
                    path = root / role / "verify.pem"
                    path.chmod(0o600)
                    write(path, public)
                path = root / "broker" / "signing.key"
                path.chmod(0o600)
                write(path, private_bytes(replacement))
                for role in ("validator", "reader"):
                    docker("start", containers[role])
                    current = json.loads(docker("inspect", containers[role]))[0]
                    assert current["Mounts"] == inspected[role]["Mounts"]
                    for network, previous in inspected[role]["NetworkSettings"]["Networks"].items():
                        actual = current["NetworkSettings"]["Networks"][network]
                        assert actual["IPAddress"] == previous["IPAddress"]
                        assert actual["NetworkID"] == previous["NetworkID"]
                    docker(
                        "exec",
                        "-d",
                        containers[role],
                        "python",
                        "-m",
                        "ciq_worker_runtime.mtls_probe",
                        "serve",
                        role,
                    )
                    ready(role)
                    assert replay_digest(role) == digests[role]
                check("fresh")  # Rules out unavailable membership/listeners/TLS.
                check("reject-old-parent")
                # Capabilities stay off logs/argv; only this test controller
                # transports the old child from broker tmpfs to reader stdin.
                child = docker("exec", containers["broker"], "cat", "/tmp/old-child")
                docker(
                    "exec",
                    "-i",
                    containers["reader"],
                    "python",
                    "-m",
                    "ciq_worker_runtime.mtls_probe",
                    "reject-old-child",
                    "reader",
                    input=child,
                )
                del child
                print("PASS: stopped-authority signing transition with retained replay volumes")

            if retained_replay:
                check("prepare-restart")
                for role, action, caller in (
                    ("validator", "replay-child", "reader"),
                    ("reader", "replay-parent", "broker"),
                ):
                    docker("restart", "--time", "1", containers[role])
                    current = json.loads(docker("inspect", containers[role]))[0]
                    for network, previous in inspected[role]["NetworkSettings"]["Networks"].items():
                        actual = current["NetworkSettings"]["Networks"][network]
                        assert actual["IPAddress"] == previous["IPAddress"]
                        assert actual["NetworkID"] == previous["NetworkID"]
                    docker(
                        "exec",
                        "-d",
                        containers[role],
                        "python",
                        "-m",
                        "ciq_worker_runtime.mtls_probe",
                        "serve",
                        role,
                    )
                    ready(role)
                    docker(
                        "exec",
                        containers[caller],
                        "python",
                        "-m",
                        "ciq_worker_runtime.mtls_probe",
                        action,
                        caller,
                        capture=False,
                    )
                check("fresh")
                for role in volumes:
                    docker(
                        "exec",
                        containers[role],
                        "python",
                        "-m",
                        "ciq_worker_runtime.mtls_probe",
                        "audit-replay",
                        role,
                        capture=False,
                    )

            def missing_replay_denied():
                # Destructive check is last: do not let missing replay state mask
                # an independent trust, membership, grant or database failure.
                check("fresh")
                docker(
                    "exec",
                    containers["reader"],
                    "python",
                    "-m",
                    "ciq_worker_runtime.mtls_probe",
                    "remove-replay",
                    "reader",
                )
                check("deny-storage")
                docker(
                    "exec",
                    containers["reader"],
                    "python",
                    "-m",
                    "ciq_worker_runtime.mtls_probe",
                    "assert-missing-startup",
                    "reader",
                    capture=False,
                )
                docker(
                    "exec",
                    containers["reader"],
                    "python",
                    "-m",
                    "ciq_worker_runtime.mtls_probe",
                    "assert-missing-replay",
                    "reader",
                    capture=False,
                )
                print(
                    "PASS: retained per-authority volumes; restart replay and missing-file denial"
                )

            if retained_replay and not database:
                missing_replay_denied()
                return
            check("check")
            docker(
                "exec",
                containers["reader"],
                "python",
                "-m",
                "ciq_worker_runtime.mtls_probe",
                "self-deny",
                "reader",
                capture=False,
            )
            if database:
                if verified_db_tls:

                    def db_probe(action):
                        docker(
                            "exec",
                            containers["membership"],
                            "python",
                            "-m",
                            "ciq_membership_runtime.db_probe",
                            action,
                            capture=False,
                        )

                    db_probe("tls-check")
                    db_probe("tls-hostname")
                    db_probe("plaintext-denied")
                    db_probe("factory-ambient")
                    ca_path = root / "membership" / "db-ca.pem"
                    # Existing engine and server remain running. Each new libpq
                    # connection must reload/verify the explicitly mounted CA.
                    for certificate, action in (
                        (database.wrong_ca_pem, "tls-ca"),
                        (None, "tls-missing-ca"),
                    ):
                        if certificate is None:
                            ca_path.unlink()
                        else:
                            ca_path.chmod(0o600)
                            ca_path.write_bytes(certificate)
                            ca_path.chmod(0o444)
                        db_probe(action)
                        check("deny")
                        if ca_path.exists():
                            ca_path.chmod(0o600)
                        write(ca_path, database.ca_pem)
                        db_probe("tls-check")
                        check("fresh")
                    print("PASS: bad/missing DB trust denies delegated delivery; restore succeeds")
                # Same running membership service/engine; every check opens a fresh connection.
                database.sql("UPDATE ops.tenant_membership SET role='medical_officer';")
                check("deny")  # Old nonclinical capability cannot cross disclosure boundaries.
                database.sql("UPDATE ops.tenant_membership SET role='auditor';")
                check("check")  # Auditor remains legitimately nonclinical for this read.
                for table in ("app_user", "tenant", "tenant_membership"):
                    database.sql(f"UPDATE ops.{table} SET active=false;")
                    check("deny")
                    database.sql(f"UPDATE ops.{table} SET active=true;")
                    check("check")
                database.sql("REVOKE SELECT(role) ON ops.tenant_membership FROM membership_test;")
                check("deny")
                database.sql("GRANT SELECT(role) ON ops.tenant_membership TO membership_test;")
                check("check")
                if retained_replay:
                    # Pause rather than stop: stopping this tmpfs-only database
                    # destroys its cluster. Resume the same state, never reseed
                    # it to simulate recovery or let ledger loss mask outage.
                    docker("pause", containers["db"])
                    try:
                        check("deny")
                    finally:
                        docker("unpause", containers["db"])
                    db_probe("tls-check")
                    missing_replay_denied()
                    print("PASS: combined retained replay and fixed-factory DB TLS lifecycle")
                else:
                    docker("stop", "--time", "1", containers["db"])
                    check("deny")
                print(
                    "PASS: restricted DB through pinned mTLS/delegated workers; no fixture fallback"
                )
                return
            # Deliberately change only this synthetic test membership file, same mount inode.
            state_path.chmod(0o600)
            state_path.write_text(json.dumps({"role": None}))
            state_path.chmod(0o444)
            check("deny")
            state_path.chmod(0o600)
            state_path.write_text(json.dumps({"role": "processor"}))
            state_path.chmod(0o444)
            check("check")  # Restoration succeeds before testing independent service outage.
            docker("stop", "--time", "1", containers["membership"])
            check("deny")
            print("PASS: four private containers; real mTLS delegation/membership; synthetic only")
    finally:
        failures = []
        for command in (
            *[("rm", "-f", cid) for cid in reversed(list(containers.values()))],
            *[("network", "rm", network) for network in reversed(networks)],
            *[("volume", "rm", volume) for volume in reversed(list(volumes.values()))],
            ("image", "rm", image),
            *([("image", "rm", membership_image)] if restricted_db else []),
        ):
            result = subprocess.run(
                ["docker", *command], capture_output=True, text=True, timeout=30
            )
            if result.returncode and "No such" not in result.stderr:
                failures.append(command[0])
        if failures:
            raise RuntimeError(f"Test cleanup incomplete for {prefix}: {failures}")
        print("PASS: invocation-owned mTLS containers/networks/volumes/image tags removed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--retained-replay", action="store_true")
    modes.add_argument("--restricted-db", action="store_true")
    modes.add_argument("--verified-db-tls", action="store_true")
    modes.add_argument("--retained-replay-tls", action="store_true")
    modes.add_argument("--signing-generation-tls", action="store_true")
    args = parser.parse_args()
    main(
        retained_replay=args.retained_replay
        or args.retained_replay_tls
        or args.signing_generation_tls,
        restricted_db=args.restricted_db,
        verified_db_tls=args.verified_db_tls
        or args.retained_replay_tls
        or args.signing_generation_tls,
        signing_generation=args.signing_generation_tls,
    )
