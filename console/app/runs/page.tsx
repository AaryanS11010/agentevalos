import { api } from "@/lib/api";

export default async function RunsPage() {
  const runs = await api.listRuns().catch(() => []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Agent Runs</h1>
      <table className="w-full text-sm">
        <thead className="text-left text-slate-400">
          <tr>
            <th className="py-2">ID</th>
            <th>Industry</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id} className="border-t border-slate-800">
              <td className="py-2 font-mono text-xs">{run.id}</td>
              <td>{run.industry}</td>
              <td>{run.status}</td>
            </tr>
          ))}
          {runs.length === 0 && (
            <tr>
              <td colSpan={3} className="py-4 text-slate-500">
                No runs yet — POST /runs on the agent-orchestrator to create one.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
