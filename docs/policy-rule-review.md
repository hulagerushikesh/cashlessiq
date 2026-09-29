# Policy rule human-review gate

## Selected source

- Product: Arogya Sanjeevani Policy, The New India Assurance Co. Ltd
- UIN: `NIAHLIP25044V022425`
- Version recorded by CashlessIQ: `V02 2024-25`
- Official source: <https://www.newindia.co.in/assets/docs/know-more/health/arogya-sanjeevani/POLICY%20CLAUSES%20Arogya%20Sanjeevani.pdf>
- PDF metadata creation date observed: 6 March 2025

The values below were checked against the selected PDF and approved by Rushikesh.

| Rule | Clause/page | Parameter to verify | Status |
|---|---|---|---|
| Room cap | 4.1(a), p.7 | 2% SI, max INR 5,000/day | Verified |
| ICU cap | 4.1(b), p.7 | 5% SI, max INR 10,000/day | Verified |
| Proportionate deduction | 4.1 Note (b), p.8 | Applies to other hospital expenses; medicines exempt | Verified |
| Cataract sublimit | 4.3, p.8 | 25% SI or INR 40,000, lower, per eye/year | Verified |
| PED waiting | 6.1, p.9 | 36 months continuous coverage | Verified |
| Specific waiting | 6.2(i), p.10 | Listed conditions including cataract/hernia: 24 months | Verified |
| Specific waiting | 6.2(ii), p.10 | Joint replacement/age-related OA/osteoporosis: 36 months | Verified |
| Initial waiting | 6.3, p.10 | 30 days; covered accidents exempt | Verified |
| Refractive error exclusion | 7.12, p.12 | Correction below 7.5 dioptres excluded | Verified |
| Co-payment | 9.5, p.15 | 5% of admissible payable claim | Verified |

## Items requiring an explicit decision

1. **Resolved:** use the operative clause 6.1 value of 36 months for PED waiting.
2. **Resolved:** apply the mandatory 5% co-payment to all admissible payable cases; therefore clean and
   accident-exempt cases are `APPROVE_WITH_DEDUCTIONS` rather than full `APPROVE`.

## Sign-off

- Reviewer name: Rushikesh
- Review date/time (IST): 2026-09-29 23:30
- Source PDF SHA-256: `890ab4794c98a56eda8ef2749124e2114589cc00a5e596bed0392ea13667efce`
- Decisions on items 1 and 2: 36-month PED; mandatory 5% co-pay applied
- Approved to populate `VERIFIED_BY` / `VERIFIED_AT`: Yes
