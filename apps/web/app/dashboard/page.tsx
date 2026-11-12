"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type Analytics } from "@/lib/api";

export default function Dashboard() {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Analytics>("/analytics/overview").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p>Loading…</p>;
  const events = Object.entries(data.events_by_type).map(([type, count]) => ({ type, count }));
  const offline = [...data.offline_metrics].sort((a, b) => Number(b["ndcg@10"]) - Number(a["ndcg@10"]));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold">Analytics</h1>
        <p className="text-sm text-gray-600">
          Active model: {data.active_model_version ?? "none"} · live store activity only (synthetic events excluded)
        </p>
      </div>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-semibold">Recommendation click-through by model version</h2>
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500">
              <th>Version</th>
              <th>Impressions</th>
              <th>Clicks</th>
              <th>CTR</th>
            </tr>
          </thead>
          <tbody>
            {data.recommendation_stats.map((s) => (
              <tr key={s.model_version} className="border-t">
                <td className="py-1">{s.model_version}</td>
                <td>{s.impressions}</td>
                <td>{s.clicks}</td>
                <td>{(s.ctr * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.recommendation_stats.length === 0 && (
          <p className="mt-2 text-sm text-gray-500">No impressions logged yet.</p>
        )}
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-semibold">Store events by type</h2>
        <div className="mt-3 h-64">
          <ResponsiveContainer>
            <BarChart data={events}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="type" fontSize={12} />
              <YAxis allowDecimals={false} fontSize={12} />
              <Tooltip />
              <Bar dataKey="count" fill="#4f46e5" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {offline.length > 0 && (
        <section className="rounded-lg border bg-white p-4">
          <h2 className="font-semibold">Offline evaluation (test period, K = 10)</h2>
          <p className="text-xs text-gray-500">Computed by the evaluation scripts on held-out Amazon reviews.</p>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500">
                <th>Model</th>
                <th>NDCG@10</th>
                <th>Recall@10</th>
                <th>MAP@10</th>
                <th>Coverage@10</th>
              </tr>
            </thead>
            <tbody>
              {offline.map((m) => (
                <tr key={String(m.model)} className="border-t">
                  <td className="py-1">{m.model}</td>
                  <td>{Number(m["ndcg@10"]).toFixed(4)}</td>
                  <td>{Number(m["recall@10"]).toFixed(4)}</td>
                  <td>{Number(m["map@10"]).toFixed(4)}</td>
                  <td>{Number(m["coverage@10"]).toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
