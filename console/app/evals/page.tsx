export default function EvalsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Evals</h1>
      <p className="text-slate-400 max-w-2xl">
        DeepEval regression results and Promptfoo red-team findings render here. Wire this
        page up to eval-engine&apos;s <code>/redteam/run</code> and a future{" "}
        <code>/evals</code> read endpoint once those are ready — see{" "}
        <code>services/eval-engine/app/api</code>.
      </p>
    </div>
  );
}
