# Dataset register

Only synthetic member/clinical data and publicly available policy documents are used.

## CashlessIQ fixed-seed synthetic dataset v1

- **Publisher / generator:** CashlessIQ contributors; Faker `en_IN` 37.x, seed 42
- **Source URL:** Repository `data_gen/`
- **License:** MIT (repository license)
- **Retrieved on:** Generated reproducibly; reference date 2026-09-29
- **Files used:** Generated CSVs and 50 generic pre-authorisation PDFs
- **Purpose:** Demonstration, extraction evaluation, and deterministic rules testing
- **Synthetic or public:** Synthetic
- **Contains real patient or insurer data:** No
- **Integrity / human verification:** Counts and golden matrix are enforced by pytest
- **Attribution required:** Faker project attribution in repository documentation

## Arogya Sanjeevani Policy, The New India Assurance Co. Ltd

- **Name and version:** UIN NIAHLIP25044V022425, V02 2024-25
- **Publisher:** The New India Assurance Co. Ltd
- **Source URL:** https://www.newindia.co.in/assets/docs/know-more/health/arogya-sanjeevani/POLICY%20CLAUSES%20Arogya%20Sanjeevani.pdf
- **License:** Public insurer policy wording; copyright remains with the publisher
- **Retrieved on:** 2026-09-29
- **Files used:** Official policy clauses PDF
- **Purpose:** Sole primary policy source for clause retrieval and rule parameters
- **Synthetic or public:** Public
- **Contains real patient or insurer data:** No patient data; publisher identity is retained for attribution
- **Integrity / human verification:** SHA-256 `890ab4794c98a56eda8ef2749124e2114589cc00a5e596bed0392ea13667efce`; rule review pending
- **Attribution required:** Insurer, product name, UIN, and source link

## Future entry template

- **Name and version:**
- **Publisher / generator:**
- **Source URL:**
- **License and license URL:**
- **Retrieved on:**
- **Files used:**
- **Purpose:**
- **Synthetic or public:**
- **Contains real patient or insurer data:** Must be `No`
- **Integrity / human verification:**
- **Attribution required:**
