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

The hackathon submission is complete. Active work is product development;
video, deck, and submission packaging are no longer active milestones.
Product P0 is approved, and P1 engineering CI passes. Rushikesh approved
deferring interviews to begin the read-only P2 synthetic alpha; workflow
assumptions remain unvalidated and real patient data is not permitted.
The Snowflake/Streamlit setup above describes the retained prototype; the new
product workspace runs independently as described below.

## Product direction

For the current phase, completed work, remaining gates and next steps, use the
[product progress checklist](docs/product/progress.md).

The productization plan preserves the deterministic rules core and human
approval gate while separating the production web application, workflow API,
asynchronous workers, and Snowflake intelligence services. Start with the
[product requirements](docs/product/product-requirements.md),
[target architecture](docs/architecture/target-architecture.md), and
[migration plan](docs/architecture/migration-plan.md). Product Phase P0 status
is tracked in the [P0 checklist](docs/product/phase-p0-checklist.md).
P0 is approved; P1 progress is tracked in the
[P1 checklist](docs/product/phase-p1-checklist.md). Before restructuring, preserve
the [migration contracts](docs/architecture/contract-versioning.md) and follow the
[Snowflake budget plan](docs/product/snowflake-budget.md).

### Local product workspace

With Docker Compose and Python 3.11 installed:

```sh
make product-up
```

Open [localhost:3000](http://localhost:3000) and choose a synthetic reviewer role.
Use the [10-minute local alpha testing guide](docs/product/local-alpha-testing.md)
for the three role journeys, expected values and issue-reporting checklist.
The next live milestone is a **private owner preview before a customer MVP**.
Use the [joint acceptance checklist](docs/product/owner-preview-acceptance.md)
to keep engineering results and Rushikesh's human feedback separate. The local
app has been tested by Rushikesh, who also walked two friends through its
current state. That completes the general local human-testing checkpoint by
owner report; an owner-only online address is not deployed yet.
The [two-person testing/GCP plan](docs/product/gcp-private-testing.md) records
37 passing checks under small-runtime limits and a final approximately 190 MiB
combined service snapshot. Local Docker is sufficient for current testing; a
dedicated GCP project is prepared without billing for an independent preview.
The earlier [Mac preview package](docs/product/mac-owner-preview.md) remains an
optional route, not a prerequisite to keep developing.
The [case queue](http://localhost:3000/cases) now supports read-only exploration
of three golden scenarios, calculation traces, and policy source references.
See the [P2 checklist](docs/product/phase-p2-checklist.md) for scope and limits.
The local **UI preview** navigation opens `/source-preview`: authenticated,
fictional fixtures for saved, missing, query, referral and unavailable states.
Choose **Evidence** to try the clause-register ID/title filter, result count,
clear-filter state and page links. These fictional Example.org PDF links are
placeholders, not real policy documents or validated supporting evidence.
It exercises v2 presentation only, not source/API parity or tenant isolation;
it never calls Snowflake and returns 404 outside local/local-auth mode.
`npm run test:client` checks the not-yet-connected v2 HTTP-client boundary using
injected responses only; no browser, server or Snowflake credentials required.
`make product-test-source-ui` additionally exercises the gated source screens
through a real temporary API and PostgreSQL memberships with fake source gateways.
It uses ports 3003/8003 and disposable test identities; normal startup and the
public website remain unchanged. See the local-development guide for boundaries.
The stack runs Next.js, FastAPI, PostgreSQL, and Redis locally. It does not call
Snowflake or AI services. Stop it with `make product-down`; local database data
is retained. See [local development](docs/architecture/local-development.md)
for tests, generated API contracts, and identity configuration.
