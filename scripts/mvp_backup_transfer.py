"""Encrypt or recover a verified synthetic MVP backup with a GPG key.

This is an offline transfer helper. It does not create a backup, contact a
remote store, or change a running database. Use a recipient fingerprint whose
private key is available on the recovery host.
"""

import argparse
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from scripts.verify_mvp_backup import MAX_DUMP_BYTES, MAX_MANIFEST_BYTES, verify_package

FINGERPRINT = re.compile(r"[A-Fa-f0-9]{40}\Z")
MAX_ARCHIVE_BYTES = MAX_DUMP_BYTES + MAX_MANIFEST_BYTES + 1024**2
MAX_ENCRYPTED_BYTES = MAX_ARCHIVE_BYTES + 1024**2
FILES = {"current.dump": MAX_DUMP_BYTES, "verified.json": MAX_MANIFEST_BYTES}


def gpg_args(home: Path | None) -> list[str]:
    binary = shutil.which("gpg")
    if binary is None:
        raise ValueError("GPG is required for encrypted backup transfer")
    return [
        binary,
        "--no-options",
        *(["--homedir", str(home)] if home else []),
        "--batch",
        "--no-tty",
    ]


def encrypt_backup(source: Path, output: Path, recipient: str, *, home: Path | None = None):
    verify_package(source)
    if not FINGERPRINT.fullmatch(recipient):
        raise ValueError("Use the recipient's complete 40-character GPG fingerprint")
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Encrypted output already exists")
    if not output.parent.is_dir():
        raise ValueError("Encrypted output parent does not exist")
    with tempfile.TemporaryDirectory(prefix=".ciq-encrypt-", dir=output.parent) as temporary:
        staged = Path(temporary) / "backup.gpg"
        process = subprocess.Popen(
            [
                *gpg_args(home),
                "--yes",
                "--trust-model",
                "always",
                "--recipient",
                recipient,
                "--encrypt",
                "--output",
                str(staged),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
                for name in sorted(FILES):
                    path = source / name
                    with path.open("rb") as stream:
                        info = tarfile.TarInfo(name)
                        info.size = path.stat().st_size
                        info.mode = 0o600
                        archive.addfile(info, stream)
            process.stdin.close()
            if process.wait(timeout=30) != 0:
                raise ValueError("GPG encryption failed")
        except (OSError, subprocess.TimeoutExpired, tarfile.TarError):
            process.kill()
            process.wait()
            raise ValueError("GPG encryption failed") from None
        if not staged.is_file() or staged.stat().st_size == 0:
            raise ValueError("Encrypted backup was not created")
        staged.chmod(0o600)
        os.link(staged, output)  # Exclusive: refuse a destination created during encryption.


def decrypt_backup(source: Path, destination: Path, *, home: Path | None = None):
    source = Path(source)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Recovery destination already exists")
    if not destination.parent.is_dir():
        raise ValueError("Recovery destination parent does not exist")
    if not source.is_file() or source.is_symlink():
        raise ValueError("Expected a regular encrypted backup file")
    if not 0 < source.stat().st_size <= MAX_ENCRYPTED_BYTES:
        raise ValueError("Encrypted backup size is outside the accepted bound")
    with tempfile.TemporaryDirectory(prefix=".ciq-decrypt-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "backup"
        staged.mkdir(mode=0o700)
        process = subprocess.Popen(
            [*gpg_args(home), "--decrypt", str(source)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        try:
            archive_path = Path(temporary) / "archive.tar"
            with archive_path.open("xb") as archive_file:
                archive_path.chmod(0o600)
                total = 0
                while chunk := process.stdout.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_ARCHIVE_BYTES:
                        raise ValueError("Decrypted backup exceeds the accepted bound")
                    archive_file.write(chunk)
            if process.wait(timeout=30) != 0:
                raise ValueError("GPG decryption failed")
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
            process.wait()
            raise ValueError("GPG decryption failed") from None
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        with tarfile.open(archive_path, mode="r:") as archive:
            seen = set()
            for member in archive:
                if (
                    member.name not in FILES
                    or member.name in seen
                    or not member.isfile()
                    or not 0 < member.size <= FILES[member.name]
                ):
                    raise ValueError("Encrypted backup contains an unexpected archive entry")
                seen.add(member.name)
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("Encrypted backup contains an unreadable entry")
                target = staged / member.name
                with target.open("xb") as result:
                    target.chmod(0o600)
                    shutil.copyfileobj(stream, result)
            if seen != set(FILES):
                raise ValueError("Encrypted backup is missing a required file")
        verify_package(staged)
        # mkdir is exclusive even if another process creates the destination
        # after the initial check. Never replace an existing recovery package.
        destination.mkdir(mode=0o700)
        try:
            for name in sorted(FILES):
                os.replace(staged / name, destination / name)
        except OSError:
            for name in FILES:
                (destination / name).unlink(missing_ok=True)
            destination.rmdir()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpg-home", type=Path, help="Optional GPG keyring directory")
    commands = parser.add_subparsers(dest="action", required=True)
    export = commands.add_parser("encrypt", help="Encrypt a verified backup for transfer")
    export.add_argument("source", type=Path)
    export.add_argument("output", type=Path)
    export.add_argument("--recipient", required=True, help="Full 40-character GPG fingerprint")
    recover = commands.add_parser("decrypt", help="Recover and verify an encrypted backup")
    recover.add_argument("source", type=Path)
    recover.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "encrypt":
            encrypt_backup(args.source, args.output, args.recipient, home=args.gpg_home)
            print(
                "Encrypted backup created. Keep the recipient private key available for recovery."
            )
        else:
            decrypt_backup(args.source, args.destination, home=args.gpg_home)
            print("Backup decrypted and verified. It has not been restored to a database.")
    except (OSError, ValueError, tarfile.TarError):
        parser.exit(1, "Encrypted backup transfer failed; inspect keys, files and permissions.\n")


if __name__ == "__main__":
    main()
