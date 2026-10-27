"""Encrypted transfer uses a disposable key and fictional backup bytes."""

import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import pytest

from scripts.mvp_backup_transfer import decrypt_backup, encrypt_backup
from scripts.verify_mvp_backup import verify_package


@pytest.fixture(scope="module")
def gpg_key():
    if shutil.which("gpg") is None:
        pytest.skip("GPG is not installed")
    with tempfile.TemporaryDirectory(prefix="ciq-gpg-", dir="/tmp") as temporary:
        home = Path(temporary)
        subprocess.run(
            [
                "gpg",
                "--no-options",
                "--homedir",
                str(home),
                "--batch",
                "--pinentry-mode",
                "loopback",
                "--passphrase",
                "",
                "--quick-generate-key",
                "CashlessIQ transfer test <ciq-transfer@example.invalid>",
                "rsa2048",
                "encr",
                "0",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        listing = subprocess.check_output(
            ["gpg", "--no-options", "--homedir", str(home), "--with-colons", "--list-keys"],
            text=True,
            timeout=10,
        )
        fingerprint = next(
            row.split(":")[9] for row in listing.splitlines() if row.startswith("fpr:")
        )
        try:
            yield home, fingerprint
        finally:
            subprocess.run(
                ["gpgconf", "--homedir", str(home), "--kill", "gpg-agent"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )


@pytest.fixture
def backup(tmp_path):
    directory = tmp_path / "source"
    directory.mkdir(mode=0o700)
    contents = b"PGDMP" + b"fictional data only" * 50
    dump = directory / "current.dump"
    dump.write_bytes(contents)
    dump.chmod(0o600)
    manifest = {
        "schema": "0003_mvp",
        "tables": {
            f"table_{index}": {
                "columns": [["id", "integer", True]],
                "rows": index,
                "sha256": "a" * 64,
            }
            for index in range(10)
        },
        "dump": {
            "file": "current.dump",
            "bytes": len(contents),
            "sha256": hashlib.sha256(contents).hexdigest(),
        },
    }
    descriptor = directory / "verified.json"
    descriptor.write_text(json.dumps(manifest))
    descriptor.chmod(0o600)
    return directory


def test_encrypted_transfer_round_trip_and_exclusive_destination(backup, gpg_key, tmp_path):
    home, fingerprint = gpg_key
    encrypted = tmp_path / "bundle.gpg"
    recovered = tmp_path / "recovered"
    encrypt_backup(backup, encrypted, fingerprint, home=home)
    assert encrypted.stat().st_mode & 0o077 == 0
    assert encrypted.read_bytes()[:5] != b"PGDMP"
    with pytest.raises(ValueError, match="already exists"):
        encrypt_backup(backup, encrypted, fingerprint, home=home)
    decrypt_backup(encrypted, recovered, home=home)
    assert verify_package(recovered) == verify_package(backup)
    assert (recovered / "current.dump").read_bytes() == (backup / "current.dump").read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        decrypt_backup(encrypted, recovered, home=home)


def test_encryption_rejects_missing_recipient_without_output(backup, gpg_key, tmp_path):
    home, _ = gpg_key
    encrypted = tmp_path / "not-created.gpg"
    with pytest.raises(ValueError, match="GPG encryption failed"):
        encrypt_backup(backup, encrypted, "0" * 40, home=home)
    assert not encrypted.exists()


def test_public_key_only_export_recovers_with_separate_private_keyring(backup, gpg_key, tmp_path):
    private_home, fingerprint = gpg_key
    public_key = subprocess.check_output(
        ["gpg", "--no-options", "--homedir", str(private_home), "--export", fingerprint],
        timeout=10,
    )
    with tempfile.TemporaryDirectory(prefix="ciq-public-", dir="/tmp") as temporary:
        public_home = Path(temporary)
        subprocess.run(
            ["gpg", "--no-options", "--homedir", str(public_home), "--batch", "--import"],
            input=public_key,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        secrets = subprocess.run(
            [
                "gpg",
                "--no-options",
                "--homedir",
                str(public_home),
                "--with-colons",
                "--list-secret-keys",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert "sec:" not in secrets.stdout
        encrypted = tmp_path / "public-key-only.gpg"
        encrypt_backup(backup, encrypted, fingerprint, home=public_home)
        with pytest.raises(ValueError, match="GPG decryption failed"):
            decrypt_backup(encrypted, tmp_path / "no-private-key", home=public_home)
        recovered = tmp_path / "separate-keyring-recovery"
        decrypt_backup(encrypted, recovered, home=private_home)
        assert verify_package(recovered) == verify_package(backup)


def test_encrypted_transfer_rejects_corruption_and_wrong_key(backup, gpg_key, tmp_path):
    home, fingerprint = gpg_key
    encrypted = tmp_path / "bundle.gpg"
    encrypt_backup(backup, encrypted, fingerprint, home=home)
    data = bytearray(encrypted.read_bytes())
    data[-1] ^= 1
    encrypted.write_bytes(data)
    with pytest.raises(ValueError, match="GPG decryption failed"):
        decrypt_backup(encrypted, tmp_path / "failed", home=home)
    assert not (tmp_path / "failed").exists()
    empty_home = tmp_path / "empty-gnupg"
    empty_home.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="GPG decryption failed"):
        decrypt_backup(encrypted, tmp_path / "wrong-key", home=empty_home)


def test_encrypted_transfer_rejects_unexpected_archive_members(backup, gpg_key, tmp_path):
    home, fingerprint = gpg_key
    archive_path = tmp_path / "bad.tar"
    with tarfile.open(archive_path, "w") as archive:
        archive.add(backup / "current.dump", arcname="current.dump")
        archive.add(backup / "verified.json", arcname="verified.json")
        archive.add(backup / "verified.json", arcname="../escape")
    encrypted = tmp_path / "bad.gpg"
    subprocess.run(
        [
            "gpg",
            "--no-options",
            "--homedir",
            str(home),
            "--batch",
            "--no-tty",
            "--yes",
            "--trust-model",
            "always",
            "--recipient",
            fingerprint,
            "--encrypt",
            "--output",
            str(encrypted),
            str(archive_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    with pytest.raises(ValueError, match="unexpected archive entry"):
        decrypt_backup(encrypted, tmp_path / "recovered", home=home)
    assert not (tmp_path / "recovered").exists()
