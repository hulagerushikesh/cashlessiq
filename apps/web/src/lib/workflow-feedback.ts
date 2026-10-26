// Only fixed public messages reach the browser. Never echo API bodies or submitted facts.
export const workflowErrors: Record<string, string> = {
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
