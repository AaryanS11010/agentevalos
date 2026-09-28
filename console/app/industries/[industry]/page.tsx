import { api } from "@/lib/api";

export default async function IndustryLeaderboardPage({
  params,
}: {
  params: { industry: string };
}) {
  const { entries } = await api
    .getLeaderboard(params.industry)
    .catch(() => ({ entries: [] as Awaited<ReturnType<typeof api.getLeaderboard>>["entries"] }));

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold capitalize">{params.industry} — Model Leaderboard</h1>
      <p className="text-slate-400">Ranked by impact score (discrimination + calibration + fairness).</p>
      <table className="w-full text-sm">
        <thead className="text-left text-slate-400">
          <tr>
            <th className="py-2">Model</th>
            <th>{`Primary metric`}</th>
            <th>Calibration error</th>
            <th>Fairness gap</th>
            <th>Impact score</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.model_name} className="border-t border-slate-800">
              <td className="py-2">{e.model_name}</td>
              <td>
                {e.primary_metric_name} = {e.primary_metric_value.toFixed(3)}
              </td>
              <td>{e.calibration_error?.toFixed(3) ?? "—"}</td>
              <td>{e.fairness_gap?.toFixed(3) ?? "—"}</td>
              <td className="font-semibold">{e.impact_score.toFixed(3)}</td>
            </tr>
          ))}
          {entries.length === 0 && (
            <tr>
              <td colSpan={5} className="py-4 text-slate-500">
                No benchmark runs yet for {params.industry} — trigger one from Runs.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
