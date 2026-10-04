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

The decision path is deliberately split: Snowpark procedures call a pure-Python
rules core for waiting periods, sublimits, payable amounts, and SLA state;
Cortex Search retrieves policy evidence; the Cortex Agent orchestrates those
tools and returns strictly validated JSON. The reviewer remains responsible for
the final action, and `DENY` is not part of the output contract.

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

Review the 10-credit warehouse resource-monitor quota and every
`VERIFY WITH COCO` marker before running account setup. The trial's dollar
balance is not a Snowflake credit quota, and Cortex/serverless usage needs a
separate budget. Then run `make setup` twice to prove idempotency.

## Tests

`make test` runs the pure-Python contract tests. `make lint` runs Ruff. No
Snowflake account is needed for either command.

## Build and deploy

Run phases in order against the `cashlessiq` Snowflake connection:

```bash
make setup       # account objects; safe to run twice
make data        # fixed-seed CSV/PDF data and public policy source
make documents   # extraction, clauses, search, semantic view, acceptance gate
make agent       # deterministic procedures and Cortex Agent
make deploy      # container Streamlit app and restricted caller grants
make eval        # all 30 golden cases into EVAL tables
```

The deployed reviewer console is:
[CashlessIQ in Snowsight](https://app.snowflake.com/me-central2.gcp/ca31605/#/streamlit-apps/CASHLESSIQ_APP).

## Measured results

The latest 30-case live-agent evaluation produced 30/30 schema-valid decisions,
27/30 correct outcomes, 29/30 correct payable amounts, 55% strict citation
recall, and 41.4-second average latency. See
[docs/evaluation.md](docs/evaluation.md) for the documented gaps.

## Demo and governance

- [Three-minute demo script](docs/demo-script.md)
- [Dataset and policy-source register](docs/datasets.md)
- [CoCo prompt and approval playbook](docs/coco-playbook.md)
- [Human-reviewed policy rules](docs/policy-rule-review.md)

The three demo personas are medical officer, processor, and auditor. Snowflake
masking policies and restricted caller rights give them different visibility and
actions. The policy-onboarding skill requires an explicit human-approved diff
and rejects unsupported executable rule types.

## Project status

Phases 0–4 are tagged and complete. Phase 5 evaluation meets the required
accuracy target; final judge-login testing and submission packaging remain.
