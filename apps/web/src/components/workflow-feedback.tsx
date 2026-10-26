import { workflowErrors } from "@/lib/workflow-feedback";

export function WorkflowFeedback({
  result,
  error,
  success = "Action saved.",
}: {
  result?: string;
  error?: string;
  success?: string;
}) {
  if (!result) return null;
  const style = "mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950";
  if (result === "saved")
    return (
      <p role="status" className={style}>
        {success}
      </p>
    );
  return (
    <p role="alert" aria-label="Form error" className={style}>
      {(error && Object.hasOwn(workflowErrors, error) && workflowErrors[error]) ||
        (result === "conflict"
          ? "The record changed or a workflow requirement is not met. Refresh and review before retrying."
          : "Action was not saved. Check the form and your role, then retry.")}
    </p>
  );
}
