-- Temporary Phase 0 Agent used only to prove container-runtime connectivity.
USE ROLE CIQ_ADMIN;
USE DATABASE CASHLESSIQ;
USE SCHEMA AI;

CREATE AGENT IF NOT EXISTS CIQ_SPIKE_AGENT
  COMMENT = 'Temporary Phase 0 connectivity spike'
  FROM SPECIFICATION
  $$
  models:
    orchestration: auto

  instructions:
    response: "You are a connectivity-test assistant. Follow the user request and reply briefly."
  $$;

GRANT USAGE ON AGENT CASHLESSIQ.AI.CIQ_SPIKE_AGENT TO ROLE CIQ_APP_USER;

