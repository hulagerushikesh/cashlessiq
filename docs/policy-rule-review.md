# Policy rule human-review gate

## Selected source

- Product: Arogya Sanjeevani Policy, The New India Assurance Co. Ltd
- UIN: `NIAHLIP25044V022425`
- Version recorded by CashlessIQ: `V02 2024-25`
- Official source: <https://www.newindia.co.in/assets/docs/know-more/health/arogya-sanjeevani/POLICY%20CLAUSES%20Arogya%20Sanjeevani.pdf>
- PDF metadata creation date observed: 6 March 2025

Do not set `VERIFIED_BY` or `VERIFIED_AT` until every row below is checked against that PDF.

| Rule | Clause/page | Parameter to verify | Status |
|---|---|---|---|
| Room cap | 4.1(a), p.7 | 2% SI, max INR 5,000/day | Pending |
| ICU cap | 4.1(b), p.7 | 5% SI, max INR 10,000/day | Pending |
| Proportionate deduction | 4.1 Note (b), p.8 | Applies to other hospital expenses; medicines exempt | Pending |
| Cataract sublimit | 4.3, p.8 | 25% SI or INR 40,000, lower, per eye/year | Pending |
| PED waiting | 6.1, p.9 | 36 months continuous coverage | Pending |
| Specific waiting | 6.2(i), p.10 | Listed conditions including cataract/hernia: 24 months | Pending |
| Specific waiting | 6.2(ii), p.10 | Joint replacement/age-related OA/osteoporosis: 36 months | Pending |
| Initial waiting | 6.3, p.10 | 30 days; covered accidents exempt | Pending |
| Refractive error exclusion | 7.12, p.12 | Correction below 7.5 dioptres excluded | Pending |
| Co-payment | 9.5, p.15 | 5% of admissible payable claim | Pending |

## Items requiring an explicit decision

1. The operative PED clause 6.1 says 36 months, but the customer-information sheet embedded later in
   the same PDF says four years. The generated rule uses 36 months because the numbered contract clause
   is the operative wording. Confirm this interpretation.
2. Clause 9.5 mandates 5% co-payment. The build-plan golden matrix nevertheless defines six clean cases
   as `APPROVE` with no deduction. Confirm whether the hackathon outcome should treat mandatory co-pay
   as a deduction (making those cases `APPROVE_WITH_DEDUCTIONS`) or preserve the matrix as written.

## Sign-off

- Reviewer name:
- Review date/time (IST):
- Source PDF SHA-256: `890ab4794c98a56eda8ef2749124e2114589cc00a5e596bed0392ea13667efce`
- Decisions on items 1 and 2:
- Approved to populate `VERIFIED_BY` / `VERIFIED_AT`: Yes / No
