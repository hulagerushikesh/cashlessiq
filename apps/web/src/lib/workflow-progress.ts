// Read projections only. No facts, credentials or editable command versions cross this boundary.
export type ProcessingJob = { id: string; state: string; attempts: number } | null;
export type Assessment = {
  outcome: string;
  payable_inr: number | null;
  policy_version: string;
  policy_id: string;
  input_digest: string;
  rules_digest: string;
  queries?: string[];
  refer_reasons?: string[];
  payable?: {
    lines: {
      item: string;
      payable_inr: number;
      reason: string;
      calc: string;
      citations: { id: string }[];
    }[];
  } | null;
};
export type Documents = {
  clinical_restricted: boolean;
  items: {
    id: string;
    state: string;
    digest: string;
    text: string | null;
    processing_job: ProcessingJob;
  }[];
};
export type RequestProgress = {
  assessment: Assessment | null;
  assessment_job: ProcessingJob;
  clinical_restricted: boolean;
  documents: Documents;
};
export type PolicyProgress = {
  regression_job_id: string | null;
  regression_state: string;
  regression: {
    passed: boolean;
    count: number;
    checks: {
      name: string;
      passed: boolean;
      actual_outcome: string;
      actual_payable_inr: number | null;
    }[];
  } | null;
};
export function pendingJob(job: ProcessingJob) {
  return job?.state === "queued" || job?.state === "running";
}
export function requestPending(data: RequestProgress) {
  return (
    pendingJob(data.assessment_job) ||
    (!data.assessment && data.assessment_job?.state === "succeeded") ||
    documentsPending(data.documents)
  );
}
export function documentsPending(data: Documents) {
  // A worker can commit between the document and job reads. Observe again until
  // the released document/result is visible, rather than stopping on that race.
  return data.items.some(
    (d) =>
      d.state === "quarantined" &&
      (pendingJob(d.processing_job) || d.processing_job?.state === "succeeded"),
  );
}
export function policyPending(data: PolicyProgress) {
  return ["queued", "running"].includes(data.regression_state);
}
