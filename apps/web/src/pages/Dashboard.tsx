import { Activity, Cpu, MousePointerClick, Target } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type Analytics } from "@/lib/api";

const DARK = "#7A1426";
const SOFT = "#C9A97E";
const NEUTRAL = "#DCCBB1";
const BRAND = "#9E1B32";

function Kpi({ icon, label, value, note }: { icon: ReactNode; label: string; value: string; note?: string }) {
  return (
    <div className="rounded-3xl bg-surface p-5 shadow-card">
      <div className="flex items-center gap-2 text-ink-muted">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-mist text-brand-dark">{icon}</span>
        <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
      </div>
      <p className="mt-3 font-display text-3xl">{value}</p>
      {note && <p className="mt-1 text-xs text-ink-muted">{note}</p>}
    </div>
  );
}

function Card({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl bg-surface p-6 shadow-card">
      <h2 className="text-xl">{title}</h2>
      {subtitle && <p className="mt-1 text-xs text-ink-muted">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

const tooltipStyle = { borderRadius: 12, border: "none", boxShadow: "0 8px 24px rgba(28,25,23,.12)", fontSize: 12 };

export default function Dashboard() {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Analytics>("/analytics/overview").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-brand">{error}</p>;
  if (!data)
    return (
      <div className="grid gap-4 sm:grid-cols-4" aria-hidden="true">
        {Array.from({ length: 4 }, (_, i) => <div key={i} className="h-32 animate-pulse rounded-3xl bg-mist" />)}
      </div>
    );

  const impressions = data.recommendation_stats.reduce((n, s) => n + s.impressions, 0);
  const clicks = data.recommendation_stats.reduce((n, s) => n + s.clicks, 0);
  const events = Object.entries(data.events_by_type).map(([type, count]) => ({ type: type.replace(/_/g, " "), count }));
  const totalEvents = events.reduce((n, e) => n + e.count, 0);
  const offline = [...data.offline_metrics]
    .sort((a, b) => Number(b["ndcg@10"]) - Number(a["ndcg@10"]))
    .map((m) => ({ ...m, model: String(m.model), ndcg: Number(m["ndcg@10"]) }) as Record<string, string | number> & {
      model: string;
      ndcg: number;
    });
  const best = offline[0];

  return (
    <div className="space-y-8">
      <div>
        <p className="eyebrow">Recommendation insights</p>
        <h1 className="mt-1 text-4xl">How the recommender performs</h1>
        <p className="mt-2 text-sm text-ink-muted">
          Live store activity (real events only; synthetic events are excluded) and offline results on held-out reviews.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi icon={<Cpu size={15} />} label="Active model" value={data.active_model_version?.replace("hybrid-", "Hybrid ") ?? "None"} note="Serving personal recommendations" />
        <Kpi icon={<Target size={15} />} label="Impressions" value={impressions.toLocaleString()} note="Recommended products shown" />
        <Kpi icon={<MousePointerClick size={15} />} label="Click-through" value={impressions ? `${((clicks / impressions) * 100).toFixed(1)}%` : "–"} note={`${clicks} ${clicks === 1 ? "click" : "clicks"} on recommendations`} />
        <Kpi icon={<Activity size={15} />} label="Store events" value={totalEvents.toLocaleString()} note="Views, clicks, searches, saves" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Click-through by model version" subtitle="Each recommendation is logged with the model that produced it.">
          {data.recommendation_stats.length === 0 ? (
            <p className="text-sm text-ink-muted">No recommendations shown yet.</p>
          ) : (
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={data.recommendation_stats.map((s) => ({ ...s, ctrPct: +(s.ctr * 100).toFixed(2) }))}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EDE3D3" />
                  <XAxis dataKey="model_version" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis unit="%" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v}%`, "CTR"]} cursor={{ fill: "#F3ECE1" }} />
                  <Bar dataKey="ctrPct" radius={[8, 8, 0, 0]}>
                    {data.recommendation_stats.map((s, i) => <Cell key={s.model_version} fill={i === 0 ? DARK : SOFT} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card title="Store activity" subtitle="Events logged by the store, by type.">
          {events.length === 0 ? (
            <p className="text-sm text-ink-muted">No activity yet. Browse the store to generate some.</p>
          ) : (
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={events} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#EDE3D3" />
                  <XAxis type="number" allowDecimals={false} fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis type="category" dataKey="type" fontSize={11} tickLine={false} axisLine={false} width={90} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#F3ECE1" }} />
                  <Bar dataKey="count" fill={SOFT} radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      {offline.length > 0 && (
        <Card
          title="Offline evaluation: NDCG@10 on the test period"
          subtitle={`Computed by the evaluation scripts on held-out Amazon reviews.${best ? ` Best: ${best.model}.` : ""}`}
        >
          <div className="h-80">
            <ResponsiveContainer>
              <BarChart data={offline} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#EDE3D3" />
                <XAxis type="number" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="model" fontSize={11} tickLine={false} axisLine={false} width={130} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => [Number(v).toFixed(4), "NDCG@10"]} cursor={{ fill: "#F3ECE1" }} />
                <Bar dataKey="ndcg" radius={[0, 8, 8, 0]}>
                  {offline.map((m, i) => <Cell key={m.model} fill={i === 0 ? BRAND : m.model.startsWith("random") ? NEUTRAL : SOFT} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-ink-muted">
                  <th className="py-2">Model</th><th>NDCG@10</th><th>Recall@10</th><th>MAP@10</th><th>Coverage@10</th>
                </tr>
              </thead>
              <tbody>
                {offline.map((m, i) => (
                  <tr key={m.model} className={`border-t border-mist ${i === 0 ? "font-semibold" : ""}`}>
                    <td className="py-2">{m.model}</td>
                    <td>{Number(m["ndcg@10"]).toFixed(4)}</td>
                    <td>{Number(m["recall@10"]).toFixed(4)}</td>
                    <td>{Number(m["map@10"]).toFixed(4)}</td>
                    <td>{Number(m["coverage@10"]).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
