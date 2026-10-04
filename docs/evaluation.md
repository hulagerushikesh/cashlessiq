# Evaluation report

Run `EVAL-E6E692A5D0E04347B06F` evaluated all 30 fixed-seed golden requests
through `CASHLESSIQ_AGENT` on commit `f0b92d9`.

| Metric | Result |
|---|---:|
| Schema valid | 30/30 |
| Outcome correct | 27/30 (90%) |
| Payable amount correct | 29/30 (96.7%) |
| Mean citation recall | 55% |
| Average latency | 41.4 seconds |

The outcome target of at least 80% passed. The three outcome mismatches were the
pre-existing-disease cases GOL024–026. Their extracted `ICD10_CODE` value was the
literal string `None`, so the deterministic PED matcher could not link the case
to the correctly declared E11.6 condition. GOL029 was the only payable mismatch:
the loaded policy and claims produced ₹644,100 remaining sum insured instead of
the golden scenario's explicit ₹45,000 override.

Citation recall is intentionally strict. It counts expected clause IDs present
in decision line citations. QUERY and REFER responses have no payable lines, and
the current schema has no decision-level citations field, so those cases score
zero even when their reason text is correct. Accident-exemption cases cite the
co-pay line but omit the exception clause. These are documented product gaps;
the scorecard does not hide or re-label them.
