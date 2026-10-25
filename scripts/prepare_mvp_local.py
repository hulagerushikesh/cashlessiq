"""Prepare locked pure Python/JavaScript overlays for existing local images.

No Docker build, service creation, credentials, cloud or billing operation. This
development overlay does not update the underlying image. Fresh image builds use
the committed lockfile and Dockerfile instead.
"""

import hashlib
import io
import json
import subprocess
import tarfile
import tomllib
from base64 import b64decode
from pathlib import Path
from urllib.request import urlopen

from scripts.check_domain_package import verify_wheel

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/mvp-local"


def prepare_uri_parser():
    package = json.loads((ROOT / "package-lock.json").read_text())["packages"][
        "node_modules/fast-uri"
    ]
    if not package["resolved"].startswith("https://registry.npmjs.org/fast-uri/-/"):
        raise ValueError("Expected locked public URI-parser artifact")
    algorithm, expected = package["integrity"].split("-", 1)
    if algorithm != "sha512":
        raise ValueError("Expected SHA-512 package integrity")
    with urlopen(package["resolved"], timeout=15) as response:
        content = response.read(2 * 1024**2 + 1)
    if len(content) > 2 * 1024**2 or hashlib.sha512(content).digest() != b64decode(
        expected, validate=True
    ):
        raise ValueError("URI-parser integrity mismatch")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or path.parts[0] != "package":
                raise ValueError("Unexpected package path")
            if member.isdir():
                continue
            if not member.isfile() or member.size > 1024**2:
                raise ValueError("Unexpected package entry")
            files[Path(*path.parts[1:])] = archive.extractfile(member).read()
    if sum(map(len, files.values())) > 5 * 1024**2:
        raise ValueError("Package extraction limit")
    manifest = json.loads(files[Path("package.json")])
    if (
        manifest["name"] != "fast-uri"
        or manifest["version"] != package["version"]
        or manifest.get("dependencies")
    ):
        raise ValueError("Expected dependency-free locked URI parser")
    destination = OUTPUT / "node/fast-uri"
    for path, body in files.items():
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    return package


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "uv",
            "build",
            "--wheel",
            str(ROOT / "packages/domain"),
            "--out-dir",
            str(OUTPUT / "dist"),
        ],
        check=True,
        cwd=ROOT,
    )
    wheels = list((OUTPUT / "dist").glob("cashlessiq_domain-*.whl"))
    if len(wheels) != 1:
        raise ValueError("Expected exactly one domain wheel")
    wheel = wheels[0]
    verify_wheel(wheel)
    packages = tomllib.loads((ROOT / "apps/api/uv.lock").read_text())["package"]
    pypdf = next(p for p in packages if p["name"] == "pypdf")
    universal = [w for w in pypdf["wheels"] if w["url"].endswith("-py3-none-any.whl")]
    if len(universal) != 1:
        raise ValueError("Local refresh requires a locked universal pypdf wheel")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    requirements = OUTPUT / "pure-requirements.txt"
    requirements.write_text(
        f"{wheel.as_uri()} --hash=sha256:{digest}\n"
        f"{universal[0]['url']} --hash={universal[0]['hash']}\n"
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--target",
            str(OUTPUT / "python"),
            "--no-deps",
            "--reinstall",
            "--require-hashes",
            "-r",
            str(requirements),
        ],
        check=True,
        cwd=ROOT,
    )
    overlay = {
        "services": {
            "api": {
                "environment": {"PYTHONPATH": "/opt/ciq-local-python"},
                "volumes": [
                    {
                        "type": "bind",
                        "source": str(ROOT / "apps/api/src"),
                        "target": "/app/apps/api/src",
                        "read_only": True,
                        "bind": {"create_host_path": False},
                    },
                    {
                        "type": "bind",
                        "source": str(ROOT / "apps/api/migrations"),
                        "target": "/app/apps/api/migrations",
                        "read_only": True,
                        "bind": {"create_host_path": False},
                    },
                    {
                        "type": "bind",
                        "source": str(OUTPUT / "python"),
                        "target": "/opt/ciq-local-python",
                        "read_only": True,
                        "bind": {"create_host_path": False},
                    },
                ],
            }
        }
    }
    uri_parser = prepare_uri_parser()
    overlay["services"]["web"] = {
        "volumes": [
            {
                "type": "bind",
                "source": str(OUTPUT / "node/fast-uri"),
                "target": "/app/node_modules/fast-uri",
                "read_only": True,
                "bind": {"create_host_path": False},
            }
        ]
    }
    (OUTPUT / "compose.json").write_text(json.dumps(overlay, indent=2) + "\n")
    (OUTPUT / "manifest.json").write_text(
        json.dumps(
            {
                "domain_wheel_sha256": digest,
                "pypdf": pypdf["version"],
                "pypdf_sha256": universal[0]["hash"],
                "mode": "read_only_local_development_overlay",
                "image_rebuilt": False,
                "fast_uri": uri_parser["version"],
                "fast_uri_integrity": uri_parser["integrity"],
            },
            indent=2,
        )
        + "\n"
    )
    print("Prepared locked pure Python/JavaScript overlays; no services changed.")


if __name__ == "__main__":
    main()
