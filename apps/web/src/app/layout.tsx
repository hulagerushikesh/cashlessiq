import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CashlessIQ — Review workspace",
  description: "An evidence-led workspace for cashless pre-authorisation review.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
