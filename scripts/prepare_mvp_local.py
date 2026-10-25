"""Prepare read-only pure Python dependencies for an existing local API image.

No Docker build, service creation, credentials, cloud or billing operation. This
development overlay does not update the underlying image. Fresh image builds use
the committed lockfile and Dockerfile instead.
"""

import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

from scripts.check_domain_package import verify_wheel

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/mvp-local"


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
    (OUTPUT / "compose.json").write_text(json.dumps(overlay, indent=2) + "\n")
    (OUTPUT / "manifest.json").write_text(
        json.dumps(
            {
                "domain_wheel_sha256": digest,
                "pypdf": pypdf["version"],
                "pypdf_sha256": universal[0]["hash"],
                "mode": "read_only_local_development_overlay",
                "image_rebuilt": False,
            },
            indent=2,
        )
        + "\n"
    )
    print("Prepared locked pure Python overlay; no services changed.")


if __name__ == "__main__":
    main()
