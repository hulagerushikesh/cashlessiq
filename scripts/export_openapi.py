"""Export stable OpenAPI without connecting to any database or external service."""

import json
from pathlib import Path

from ciq_api.config import Settings
from ciq_api.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    settings = Settings(
        environment="test",
        auth_mode="local",
        local_auth_secret="contract-export-not-a-runtime-key-0000",
    )
    schema = create_app(settings).openapi()
    destination = ROOT / "packages/contracts/openapi.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Exported product OpenAPI (no database connection).")


if __name__ == "__main__":
    main()
