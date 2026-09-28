export default function OverviewPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">AgentEvalOS</h1>
      <p className="text-slate-400 max-w-2xl">
        An agent that benchmarks ML models for finance and healthcare. Go to{" "}
        <a href="/runs" className="underline">
          Runs
        </a>{" "}
        to start one, or check the Finance/Healthcare pages to see how models have
        ranked so far.
      </p>
    </div>
  );
}
