# P2 source-access findings

Date: 19 October 2026  
Evidence: Rushikesh supplied CoCo's ACCOUNTADMIN metadata review and subsequent
policy-reference results. These are reported live observations, not a new
independent Snowflake inspection by this document. The later, narrowly approved
user-default change is reported separately below; other remediation is pending.

## Reconciled review

| Area | Reported result | Product consequence |
| --- | --- | --- |
| Reader role | Exactly 13 expected direct grants; no grant options; only RUSHIKESH2001 as grantee; no roles granted to it | Direct grant reconciliation passes, not effective-privilege isolation |
| PUBLIC | AI/Cortex, agent-task, learning and compute-related capabilities | Reader is not effectively no-AI or universally read-only |
| Human identity | Initially ACCOUNTADMIN/ALL; later approved reader/empty defaults reported applied; admin roles remain available | Still unsuitable for unattended product service authentication |
| Authentication metadata | HAS_MFA false; no key pair or workload identity reported | MFA/enforcement review and a separately provisioned service identity remain necessary |
| Source policies | No row-access or projection policies on any of eight tables | Application TPA predicates are not a database isolation boundary |
| Masking | MASK_CLINICAL_TEXT on PREAUTH_FACTS.CLINICAL_NOTE only | Other source columns are not protected by this specific policy |

The eight tables are CORE.POLICY, CORE.POLICY_PRODUCT, CORE.CLAIM,
CORE.MEMBER_CONDITION, DOCS.PREAUTH_REQUEST, DOCS.PREAUTH_FACTS,
DOCS.POLICY_CLAUSE and APP.DECISION, all in CASHLESSIQ. The policy-reference
follow-up resolves the original report's unknown about attachments on these
tables; it does not establish the absence of other account exposure paths.

The supplied masking definition returns VAL when CIQ_MEDICAL_OFFICER or
CIQ_ADMIN is in the active role hierarchy, otherwise '***'. An active admin
hierarchy can therefore permit unmasked text even when the primary role is the
reader. With the reader primary role and secondary roles NONE, that particular
admin path is inactive. Our fixed metadata query does not select CLINICAL_NOTE.
This does not protect other clinical fields or make conditions non-sensitive.

## Qualifications to CoCo findings

1. F10 is a session/identity risk, not evidence of a broken masking function:
   the policy deliberately allows admin/medical hierarchies. Do not rewrite it
   to primary-role-only logic without checking existing Streamlit governance.
   IS_ROLE_IN_SESSION considers the active role hierarchy, not simply the name
   returned by CURRENT_ROLE. The human can activate an authorised role again;
   changing defaults is accident prevention, not a security boundary.
2. DEFAULT_ROLE/DEFAULT_SECONDARY_ROLES are defaults, not proof that every driver
   connection or reconnect is admin. Our local connector explicitly requests
   CIQ_PRODUCT_READER, and each gateway disables secondary roles before reads.
   Failures raise errors; no admin fallback exists. OAuth integration/session
   role restrictions also need consideration before claiming all granted roles
   are active. The review did not perform an unmasking data-read test.
3. F7's "password-only" conclusion is not supported by absent key-pair/WIF flags.
   The successful local probes used human OAuth. HAS_MFA false is an important
   finding to verify, but does not independently describe upstream IdP MFA or
   all authentication-policy enforcement. Do not test or weaken MFA here.
4. PUBLIC USAGE on a compute pool is an expanded surface, not proof that any
   reader can create a service or explicitly resume a pool: further privileges
   and configuration matter. No capability was tested by creating resources,
   invoking AI, attempting writes or reading clinical text.
5. Missing policies do not make existing synthetic probes invalid. They do
   prevent us from treating the operator identity/application filter as a
   production multi-tenant security boundary. CoCo's conditional supervised-use
   assessment is retained; customer/unattended use is not approved.

## Approved user-default change — 19 October

Rushikesh explicitly approved only DEFAULT_ROLE = CIQ_PRODUCT_READER and
DEFAULT_SECONDARY_ROLES = () for RUSHIKESH2001. CoCo's supplied before/after
report confirms both stored changes and unchanged grants. Independent
fresh-session verification is pending. A supplied screenshot verifies the reader
and empty secondary roles only after explicit USE commands; no unmasking data
test was performed. Existing
roles/grants, PUBLIC, masking, MFA, service identities and account settings are
outside this approval. See [execution packet](operator-defaults-change.md).

## Remediation sequence — approval scoped per step

1. CoCo reports the approved default primary role is now CIQ_PRODUCT_READER
   and default secondary roles are empty; existing grants are unchanged.
   This changes session defaults, not memberships, grants or masking logic.
   Existing sessions may retain their context. Fresh-session metadata checks
   must confirm the outcome; never print credentials or clinical values.
2. Rushikesh should enrol MFA through Snowflake/IdP's supported interactive flow.
   CoCo should review enforcement without sharing factors/recovery codes or
   locking out the sole administrator. MFA setup is separate from step 1.
3. Complete the PUBLIC dependency/impact review before proposing any revocation.
   Preserve CoCo, Streamlit and the submitted public demo. A new service user
   inherits PUBLIC too; no new user/view alone resolves this finding.
4. Review per-TPA service users/roles with tenant-filtered secure views as the
   initial design candidate; do not provision yet. Services must lack base-table
   access, and view ownership/grant paths must prevent bypass. A row-access
   policy design is an alternative requiring separate governance review.
5. Select hosting/authentication and an isolation strategy before unattended
   deployment. Prefer supported workload identity federation; otherwise review
   managed key-pair storage/rotation. An isolated account is an option to assess,
   not permission to buy one or exceed trial credits.

Production acceptance still requires cross-tenant/base-table denial evidence,
effective privileges/AI capability review, service credential revocation and
rotation, role-based clinical disclosure, and the existing privacy/identity
gates. No real data or deployment is authorised by this report.

## Phase status

- [x] CoCo report received, direct grants reconciled, visibility limits recorded.
- [x] Policy attachments reviewed in the supplied follow-up.
- [x] Supervised synthetic use assessed conditionally; service alternatives reviewed.
- [x] Human default changes approved and reported applied by CoCo.
- [ ] Human defaults independently verified in a fresh session without overrides.
- [x] Explicit reader/empty-secondary worksheet context verified by screenshot.
- [ ] MFA/enforcement review completed by account owner.
- [ ] PUBLIC dependency review and isolation design approved.
- [ ] Service identity and database tenant-isolation implementation verified.

The next bounded review is specified in the
[hardening follow-up packet](source-hardening-followup.md). It does not authorise
PUBLIC revocations, MFA enforcement changes or service provisioning.

P2 remains open; P3 is not started. The current web/API source opt-in remains
disabled by default. No SQL, grants, policy changes, source writes, AI calls,
deployment, push or tag accompanied this documentation update.

## Primary references checked

- [Role-hierarchy semantics of IS_ROLE_IN_SESSION](https://docs.snowflake.com/en/sql-reference/functions/is_role_in_session).
- [Access control, PUBLIC inheritance and UBAC](https://docs.snowflake.com/en/user-guide/security-access-control-overview).
- [Compute-pool privileges and implicit resume](https://docs.snowflake.com/en/developer-guide/snowpark-container-services/working-with-compute-pool).
- [Snowflake OAuth role restrictions](https://docs.snowflake.com/en/user-guide/oauth-custom).
