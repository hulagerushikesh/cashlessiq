// Only fixed public messages reach the browser. Never echo API bodies or submitted facts.
export const workflowErrors: Record<string, string> = {
  review_conflict:
    "The case changed. Your action was not applied. Open the latest record and review its state before submitting again.",
  review_validation:
    "Action was not saved. Check your role, assignment, state, amount and reason, then retry.",
  session:
    "Your session has ended. Sign in again before submitting. Your entries remain in this tab until you leave or reload it.",
  cost_total:
    "The cost lines must add up to the estimated total. Update the total or correct the expense amounts.",
  remaining_cover: "Remaining cover cannot exceed the sum insured.",
  cover_dates: "Policy inception and continuous cover must start on or before admission.",
  icu_days: "ICU days cannot exceed the planned length of stay.",
  connection:
    "The save could not be confirmed. Check the record before changing these entries; retrying unchanged entries uses the same command ID to prevent duplicate work.",
  inactive_policy:
    "This policy is approved but not active. A policy approver must activate it in the policy library before you can submit a request.",
  admission_date:
    "The selected policy does not cover this admission date. Check the policy effective dates and request admission date.",
  duplicate_policy:
    "This product and version already exist. Open the existing version in the policy library, or choose a new version.",
  regression_required:
    "The policy must pass all regression checks before approval or activation. Check its regression results first.",
  activation_changed:
    "Another policy version was activated while this page was open. Refresh, review the current active version, and try again.",
  policy_decided:
    "This policy already has a review decision. Refresh to see its current status; approved versions still need activation.",
  policy_dates:
    "This policy is not currently effective. Check its effective dates before activation.",
  wording_pending:
    "The policy wording PDF must finish safe text extraction before you can attach it to a proposal.",
  role: "Your current role cannot perform this action. Sign in with the appropriate review role using Sign out.",
  validation:
    "Check the form values, required fields and totals. Policy definitions must use supported rules and valid examples.",
  upload: "Choose a fictional PDF up to 2 MiB and tick the fictional-data confirmation.",
};

export const apiWorkflowErrors: Record<string, string> = {
  "Value error, Cost lines must equal the estimated total": "cost_total",
  "Value error, Remaining cover exceeds sum insured": "remaining_cover",
  "Value error, Cover cannot start after admission": "cover_dates",
  "Value error, ICU days exceed planned stay": "icu_days",
  "No approved active policy for this product": "inactive_policy",
  "Policy is not effective for this admission": "admission_date",
  "This product version already exists; propose a new version": "duplicate_policy",
  "Passing regression on this exact proposal is required": "regression_required",
  "Only approved regression-passing policies can activate": "regression_required",
  "Active policy changed; refresh before activation": "activation_changed",
  "This immutable proposal already has a review decision": "policy_decided",
  "Policy is not currently effective": "policy_dates",
  "Policy wording must finish safe text extraction first": "wording_pending",
};
