import type { Identity } from "@cashlessiq/api-client";

export const roleLabels: Record<Identity["role"], string> = {
  processor: "Processor",
  medical_officer: "Medical officer",
  auditor: "Auditor",
  policy_analyst: "Policy analyst",
  policy_approver: "Policy approver",
  operations_lead: "Operations lead",
  tenant_admin: "Tenant administrator",
};
