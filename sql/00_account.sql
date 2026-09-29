-- Phase 0 account bootstrap. This is the only script that uses ACCOUNTADMIN.
USE ROLE ACCOUNTADMIN;

CREATE ROLE IF NOT EXISTS CIQ_ADMIN COMMENT = 'Owns CashlessIQ project objects';
CREATE ROLE IF NOT EXISTS CIQ_APP_USER COMMENT = 'Shared runtime privileges';
CREATE ROLE IF NOT EXISTS CIQ_MEDICAL_OFFICER COMMENT = 'Clinical reviewer';
CREATE ROLE IF NOT EXISTS CIQ_PROCESSOR COMMENT = 'Pre-authorisation processor';
CREATE ROLE IF NOT EXISTS CIQ_AUDITOR COMMENT = 'Read-only auditor';

GRANT ROLE CIQ_ADMIN TO ROLE SYSADMIN;
GRANT ROLE CIQ_APP_USER TO ROLE CIQ_MEDICAL_OFFICER;
GRANT ROLE CIQ_APP_USER TO ROLE CIQ_PROCESSOR;
GRANT ROLE CIQ_APP_USER TO ROLE CIQ_AUDITOR;
GRANT ROLE CIQ_MEDICAL_OFFICER TO ROLE CIQ_ADMIN;
GRANT ROLE CIQ_PROCESSOR TO ROLE CIQ_ADMIN;
GRANT ROLE CIQ_AUDITOR TO ROLE CIQ_ADMIN;

-- Resource monitors use Snowflake credit units, not the trial's dollar balance.
-- Ten X-Small warehouse credits provide a conservative development guardrail.
-- This monitor does not cover serverless or Cortex AI consumption; inspect and
-- configure an account budget with CoCo before bulk AI work in Phase 2.
CREATE RESOURCE MONITOR IF NOT EXISTS CIQ_RM
  WITH CREDIT_QUOTA = 10
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS
    ON 50 PERCENT DO NOTIFY
    ON 75 PERCENT DO NOTIFY
    ON 90 PERCENT DO SUSPEND;

CREATE WAREHOUSE IF NOT EXISTS CIQ_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  RESOURCE_MONITOR = CIQ_RM
  COMMENT = 'CashlessIQ development warehouse';

GRANT OWNERSHIP ON WAREHOUSE CIQ_WH TO ROLE CIQ_ADMIN COPY CURRENT GRANTS;
GRANT USAGE, OPERATE ON WAREHOUSE CIQ_WH TO ROLE CIQ_APP_USER;

-- VERIFY WITH COCO: Confirm the account parameter and accepted value for the
-- hackathon account. Run SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION'
-- IN ACCOUNT first. If disabled, CoCo should apply the supported ALTER ACCOUNT.
SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT;

-- Cortex Agents authorize with the user's default role. This database-role
-- grant is expected by the current docs but must be confirmed in the account.
-- VERIFY WITH COCO: Confirm whether CORTEX_AGENT_USER is already granted via
-- PUBLIC and whether this explicit grant is valid in the account edition.
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_AGENT_USER TO ROLE CIQ_APP_USER;
