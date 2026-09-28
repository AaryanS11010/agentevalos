export default function OverviewPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">AgentEvalOS</h1>
      <p className="text-slate-400 max-w-2xl">
        Instrument, benchmark, red-team, and release AI agents. Use{" "}
        <a href="/runs" className="underline">
          Runs
        </a>{" "}
        to trigger and inspect LangGraph agent executions, and the industry pages to see
        which foundational tabular models rank highest for finance and healthcare
        workloads.
      </p>
    </div>
  );
}
