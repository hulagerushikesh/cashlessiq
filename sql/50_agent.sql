USE ROLE CIQ_ADMIN;
USE DATABASE CASHLESSIQ;
USE SCHEMA AI;
USE WAREHOUSE CIQ_WH;

CREATE OR REPLACE AGENT CASHLESSIQ_AGENT
COMMENT = 'Tool-first cashless pre-authorisation reviewer copilot'
FROM SPECIFICATION $$
models:
  orchestration: auto
orchestration:
  tool_not_accessible: reject
  budget:
    seconds: 120
    tokens: 8000
instructions:
  response: "Return one raw JSON object with exactly these top-level keys: request_id, outcome, total_claimed_inr, total_payable_inr, lines, queries, refer_reasons, summary, sla. No Markdown and no top-level citations. Each line has exactly item, claimed_inr, payable_inr, deduction_inr, reason, calc, citations. Each citation has exactly type and id. sla has exactly elapsed_min and state. Never compute or alter numbers and never output DENY."
  orchestration: "Always call tool_get_case first. Missing fields mean QUERY with empty lines and zero totals. Otherwise call tool_check_waiting_periods; any applies=true means REFER with empty lines and zero totals. Otherwise call tool_compute_payable and copy every line and citation unchanged. APPROVE if and only if total_claimed_inr equals total_payable_inr; any difference means APPROVE_WITH_DEDUCTIONS. Always call tool_sla_status. Retrieve every cited clause with clause_search filtered to the exact PRODUCT_ID, but do not add policy text or top-level fields. member_360 is context-only."
tools:
  - tool_spec:
      type: generic
      name: tool_get_case
      description: "Load non-PII policy and extracted facts. Always call first."
      input_schema:
        type: object
        properties:
          request_id:
            type: string
            description: "CashlessIQ request identifier"
        required:
          - request_id
  - tool_spec:
      type: generic
      name: tool_check_waiting_periods
      description: "Deterministically check waiting periods and exclusions"
      input_schema:
        type: object
        properties:
          request_id:
            type: string
            description: "CashlessIQ request identifier"
        required:
          - request_id
  - tool_spec:
      type: generic
      name: tool_compute_payable
      description: "Deterministically calculate integer-rupee payable lines and totals"
      input_schema:
        type: object
        properties:
          request_id:
            type: string
            description: "CashlessIQ request identifier"
        required:
          - request_id
  - tool_spec:
      type: generic
      name: tool_sla_status
      description: "Calculate the one-hour SLA state"
      input_schema:
        type: object
        properties:
          request_id:
            type: string
            description: "CashlessIQ request identifier"
        required:
          - request_id
  - tool_spec:
      type: cortex_search
      name: clause_search
      description: "Retrieve exact policy clauses filtered to the case product"
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: member_360
      description: "Context-only policy history; never calculate decisions or money"
tool_resources:
  tool_get_case:
    identifier: CASHLESSIQ.AI.TOOL_GET_CASE
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: CIQ_WH
  tool_check_waiting_periods:
    identifier: CASHLESSIQ.AI.TOOL_CHECK_WAITING_PERIODS
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: CIQ_WH
  tool_compute_payable:
    identifier: CASHLESSIQ.AI.TOOL_COMPUTE_PAYABLE
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: CIQ_WH
  tool_sla_status:
    identifier: CASHLESSIQ.AI.TOOL_SLA_STATUS
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: CIQ_WH
  clause_search:
    search_service: CASHLESSIQ.AI.CLAUSE_SEARCH
    max_results: '5'
    execution_environment:
      type: warehouse
      warehouse: CIQ_WH
  member_360:
    semantic_view: CASHLESSIQ.AI.MEMBER_360
    execution_environment:
      type: warehouse
      warehouse: CIQ_WH
$$;

GRANT USAGE ON AGENT CASHLESSIQ_AGENT TO ROLE CIQ_APP_USER;
