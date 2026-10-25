# Local synthetic alpha — owner testing guide

**25 October clarification:** the next “live” goal is a private preview for the
owner, followed by engineering and human checks before a customer MVP. Use the
[joint acceptance checklist](owner-preview-acceptance.md) to record this round.
The local app is available now; an owner-only online address has not been deployed.

23 October 2026. This is an authenticated **local development sandbox**, not a
public release, live Snowflake workspace or completed P2 acceptance. No Linux
installation or paid hosting is needed: Docker Desktop runs the local services
on the existing Mac. Keep Docker Desktop running while testing.

## Start here — about 10 minutes

1. Open [local sign-in](http://localhost:3000/login). If the app is stopped, run
   `make product-up` from the repository first. Do not enter Snowflake credentials.
2. Select **Processor · Asha Deshmukh**, then **Enter workspace**. Check the
   verified identity and synthetic organisation on the overview.
3. Open [Case queue](http://localhost:3000/cases). Expect three fixed golden
   snapshots, not current hospital requests or a live SLA queue.
4. Follow the checks below; sign out before switching roles.

| Check | Expected result |
| --- | --- |
| Open GOL001 | Draft payable ₹95,000; deterministic calculation and policy-check references; never an automatic final approval |
| Follow NIA-9.5 within GOL001 | The relevant on-page evidence/reference section is visible; this is not a new document retrieval |
| Open GOL027 | Missing-cost information query, “Please provide cost breakup.”, payable “Not calculated” rather than ₹0 |
| Open GOL024 | Referral reason, payable “Not calculated”; these are frozen golden outcomes, not saved live-source recommendations |
| Filter recommendation to QUERY | GOL027 appears; GOL001 does not |
| Search for a nonexistent reference | “No matching cases”; Reset restores the three snapshots |
| Processor or auditor opens GOL001 | Clinical narrative is restricted; “Acute appendicitis” is not shown |
| Medical officer opens GOL001 | Synthetic clinical details, including “Acute appendicitis”, are visible |
| Any of the three roles | No approve, send-query, refer, upload, assignment or policy-edit action is available |
| Sign out, then revisit `/cases/GOL001` | Redirect to sign-in; no case amounts or clinical text displayed |
| Narrow/mobile window | Queue and detail fit without horizontal page scrolling |

## Try the presentation states separately

After signing in, open [UI preview](http://localhost:3000/source-preview). Its
persistent banner says **Local UI fixture preview · No Snowflake reads**.
These are fictional UI-FIXTURE examples, not source records, tenant-isolation
evidence or clinical authorisation tests. All three roles see the same
nonclinical preview fixtures.

- **Saved:** ₹95,000 draft, without an invented full calculation trace.
- **Missing:** “No saved recommendation”, no draft payable. It is neither QUERY
  nor REFER, and does not mean zero payable.
- **Query / Refer:** a saved draft outcome with “Not calculated” payable.
- **Unavailable:** recommendation status is unknown, **not missing**; no fallback
  to a saved amount or demonstration decision.
- **Evidence:** filter three fictional clause references by ID/title; a no-match
  filter does not mean no policy evidence exists. Clear filter restores them.
  Example.org PDF links are placeholders; do not treat them as policy documents.

Do not compare the preview states with GOL024/GOL027 golden snapshots. The
separate automated source-contract test uses fake gateways and truthful MISSING
records for those IDs; it is another dataset, not a live replacement for `/cases`.
Normal `/source-cases` routes remain disabled (404).

## Report an issue

Send the route, selected synthetic role, steps, expected/actual behavior and a
screenshot if useful. Include browser/window size for layout issues. Do not send
cookies, tokens, `.env.product.local`, passwords or real patient documents.

## Stop and limitations

`make product-down` stops local services but retains PostgreSQL data. Restart
with `make product-up`. Existing local credentials stay in the ignored owner-only
environment file; do not delete it or the DB volume to troubleshoot casually.

The local role selector is development authentication, **not customer SSO**.
Keep the services bound to localhost; do not tunnel them or expose them through
the public domain. Other people cannot access this localhost URL from their own
computers. Production hosting, OIDC browser login, real source identities,
credential custody and governed live acceptance still require separate work.
This milestone spends no Snowflake/AI credits and assumes no paid account access.

## Verified checkpoint — 23 October

The owner approved the local-only milestone. `make product-up` rebuilt the web
and API images, applied migrations/idempotent seed, retained existing PostgreSQL
data, and left web/API/DB/Redis healthy. Host ports remain loopback-only.

Verified: **26 browser tests** (three new role-specific sign-out regressions),
**15 source API-to-UI fake-gateway tests**, **41 client tests**, **213 root tests**,
and **1,003 backend tests**. Typecheck, production web build, frontend/Python lint,
contract regeneration/no drift and whitespace checks pass. The backend has one
existing intentional invalid-model serializer warning. A production web build
passing does not make the running local development stack production-ready.

No new UI redesign or reviewer-write features are included. This is a refreshed,
verified testing baseline, not the governed live-source P2 exit. Remote CI for
the prior containment commit `2d10fcc` is green; this testing-guide commit's
post-push CI subsequently passed: implementation `c6a4b03`, run
[39895921707](https://github.com/hulagerushikesh/cashlessiq/actions/runs/39895921707),
checked on 23 October. The owner reports manual checks working as expected and
accepts this local baseline; live-source and public-release gates remain open.
