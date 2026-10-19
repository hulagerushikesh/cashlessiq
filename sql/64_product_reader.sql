-- P2 operator step, not included in make setup. No application writes or AI.
-- Run with CoCo after reviewing grants. Do not grant CIQ_APP_USER to this role:
-- it inherits INSERT/UPDATE privileges from the hackathon runtime.
USE ROLE ACCOUNTADMIN;
CREATE ROLE IF NOT EXISTS CIQ_PRODUCT_READER
  COMMENT = 'Synthetic product alpha: scoped source reads, no writes or AI';
GRANT USAGE ON WAREHOUSE CIQ_WH TO ROLE CIQ_PRODUCT_READER;
GRANT USAGE ON DATABASE CASHLESSIQ TO ROLE CIQ_PRODUCT_READER;
GRANT USAGE ON SCHEMA CASHLESSIQ.CORE TO ROLE CIQ_PRODUCT_READER;
GRANT USAGE ON SCHEMA CASHLESSIQ.DOCS TO ROLE CIQ_PRODUCT_READER;
GRANT SELECT ON TABLE CASHLESSIQ.CORE.POLICY TO ROLE CIQ_PRODUCT_READER;
GRANT SELECT ON TABLE CASHLESSIQ.CORE.POLICY_PRODUCT TO ROLE CIQ_PRODUCT_READER;
GRANT SELECT ON TABLE CASHLESSIQ.DOCS.PREAUTH_REQUEST TO ROLE CIQ_PRODUCT_READER;
GRANT SELECT ON TABLE CASHLESSIQ.DOCS.PREAUTH_FACTS TO ROLE CIQ_PRODUCT_READER;
-- VERIFY WITH COCO: Grant CIQ_PRODUCT_READER to the authenticated local operator
-- only after inspecting CURRENT_USER(); do not grant it to PUBLIC or app users.
-- Table privileges are sufficient for this synthetic spike, NOT tenant RLS.
-- Production needs tenant-scoped secure views and validated identity mapping.
-- No direct AI grants does NOT mean effectively AI-disabled: PUBLIC may grant
-- Cortex/USE AI FUNCTIONS and other capabilities. Inspect PUBLIC/user grants
-- with CoCo; never revoke account-wide grants automatically from this script.
-- Operator gateway sessions explicitly USE SECONDARY ROLES NONE before reads.
