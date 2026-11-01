"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { WorkflowForm } from "./workflow-form";

const Uploads = createContext<{ revision: number; uploaded: () => void } | null>(null);

// Share only an invalidation counter, never proposal values or PDF content.
export function PolicyWordingWorkspace({ children }: { children: ReactNode }) {
  const [revision, setRevision] = useState(0);
  return (
    <Uploads.Provider value={{ revision, uploaded: () => setRevision((value) => value + 1) }}>
      {children}
    </Uploads.Provider>
  );
}

export function usePolicyWordingUploads() {
  const uploads = useContext(Uploads);
  if (!uploads) throw new Error("Policy wording requires its workspace");
  return uploads;
}

export function PolicyWordingUploadForm({
  commandId: initialCommandId,
  children,
}: {
  commandId: string;
  children: ReactNode;
}) {
  const [commandId, setCommandId] = useState(initialCommandId);
  const uploads = usePolicyWordingUploads();
  return (
    <WorkflowForm
      action="/workflows/commands"
      method="post"
      encType="multipart/form-data"
      className="mt-6 max-w-5xl space-y-4 rounded-xl border bg-white p-6"
      success="PDF uploaded. Your proposal entries are still here. Extraction updates below; select the wording after extraction succeeds."
      onSaved={(form) => {
        const nextCommandId = crypto.randomUUID();
        // Only a confirmed upload gets a fresh key and clears its own controls.
        // An uncertain or failed response keeps the PDF and key for a safe retry.
        form.reset();
        setCommandId(nextCommandId);
        uploads.uploaded();
      }}
    >
      <input type="hidden" name="operation" value="policy-upload" />
      <input type="hidden" name="command_id" value={commandId} />
      {children}
    </WorkflowForm>
  );
}
