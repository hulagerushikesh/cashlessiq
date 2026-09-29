# CashlessIQ

CashlessIQ is a Snowflake-native copilot that drafts a cited, reviewable
cashless pre-authorisation recommendation within the IRDAI one-hour window.
It never denies a claim and never asks an LLM to calculate money.

## Architecture

The system combines staged pre-authorisation PDFs, Cortex document extraction,
a `MEMBER_360` semantic view, policy clauses in Cortex Search, deterministic
Snowpark tools backed by a pure-Python rules core, a Cortex Agent, and a
container-runtime Streamlit reviewer console. See
[the build plan](docs/build-plan.md) and the Phase 1 architecture document at
[docs/architecture.md](docs/architecture.md).

## Local setup

Requirements: Python 3.11, Snowflake CLI, CoCo CLI, and a Snowflake connection
named `cashlessiq` in `~/.snowflake/connections.toml`. Never put credentials in
this repository.

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
make test
make lint
```

Review the resource-monitor quota and every `VERIFY WITH COCO` marker before
running account setup. Then run `make setup` twice to prove idempotency.

## Tests

`make test` runs the pure-Python contract tests. `make lint` runs Ruff. No
Snowflake account is needed for either command.

## Project status

Phase 0 establishes infrastructure, domain types, the decision schema, and a
container-runtime connectivity spike. Later phases are intentionally left as
TODO stubs until the preceding phase exits green.

