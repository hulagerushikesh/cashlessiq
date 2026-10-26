"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Identity } from "@cashlessiq/api-client";

export function WorkflowNavigation({
  role,
  vertical = false,
}: {
  role: Identity["role"];
  vertical?: boolean;
}) {
  const pathname = usePathname();
  const links = [
    { href: "/workflows", label: "Testing workspace" },
    { href: "/workflows/requests", label: "Submitted requests" },
    ...(["processor", "medical_officer"].includes(role)
      ? [{ href: "/workflows/new", label: "New request" }]
      : []),
    { href: "/workflows/policies", label: "Policy library" },
    ...(role === "policy_analyst"
      ? [{ href: "/workflows/policies/new", label: "New policy" }]
      : []),
    { href: "/workflows/jobs", label: "Background jobs" },
    ...(["auditor", "operations_lead", "tenant_admin", "policy_approver"].includes(role)
      ? [{ href: "/workflows/events", label: "Governance history" }]
      : []),
    ...(role === "tenant_admin"
      ? [{ href: "/workflows/members", label: "Manage tenant access" }]
      : []),
  ];
  return (
    <nav
      aria-label="Workflow navigation"
      className={
        vertical
          ? "mt-3 flex flex-wrap gap-2 text-sm lg:flex-col"
          : "mx-auto flex max-w-[1480px] flex-wrap gap-2 px-5 pb-4 text-sm lg:px-9"
      }
    >
      {links.map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          aria-current={pathname === href ? "page" : undefined}
          className={`rounded-lg px-3 py-2 ${pathname === href ? "bg-teal-800 font-semibold text-white" : "bg-teal-50 text-teal-900 hover:bg-teal-100"}`}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
