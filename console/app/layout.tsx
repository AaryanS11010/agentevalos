import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentEvalOS Console",
  description: "AgentOps reviewer console — runs, evals, industry leaderboards",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="border-b border-slate-800 px-6 py-4 flex gap-6">
          <span className="font-semibold">AgentEvalOS</span>
          <Link href="/" className="text-slate-300 hover:text-white">
            Overview
          </Link>
          <Link href="/runs" className="text-slate-300 hover:text-white">
            Runs
          </Link>
          <Link href="/evals" className="text-slate-300 hover:text-white">
            Evals
          </Link>
          <Link href="/industries/finance" className="text-slate-300 hover:text-white">
            Finance
          </Link>
          <Link href="/industries/healthcare" className="text-slate-300 hover:text-white">
            Healthcare
          </Link>
        </nav>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
