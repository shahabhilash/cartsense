import { Eye, Flame, Gamepad2, Layers, Sparkles, Star, Users } from "lucide-react";
import type { Reason } from "@/lib/api";

const STYLE: Record<string, { label: string; icon: typeof Star }> = {
  also_reviewed_with: { label: "Bought together", icon: Users },
  similar_taste: { label: "Similar taste", icon: Sparkles },
  similar_content: { label: "Similar content", icon: Layers },
  similar_to_session: { label: "From your browsing", icon: Eye },
  popular_on_platform: { label: "Your platform", icon: Gamepad2 },
  trending: { label: "Trending", icon: Flame },
  general: { label: "Picked for you", icon: Star },
};

export function reasonStyle(type: string) {
  return STYLE[type] ?? STYLE.general;
}

export function ReasonChip({ reason }: { reason: Reason }) {
  const { label, icon: Icon } = reasonStyle(reason.type);
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-mist px-2 py-0.5 text-[11px] font-medium text-ink-soft">
      <Icon size={11} className="text-brand-dark" />
      {label}
    </span>
  );
}

export function ReasonList({ reasons }: { reasons: Reason[] }) {
  if (!reasons.length) return null;
  return (
    <ul className="space-y-2" aria-label="Why this was recommended">
      {reasons.map((r, i) => {
        const { label, icon: Icon } = reasonStyle(r.type);
        return (
          <li key={i} className="flex gap-2.5 rounded-xl bg-canvas-deep p-2.5 text-xs leading-relaxed text-ink-soft">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white text-brand-dark shadow-sm">
              <Icon size={13} />
            </span>
            <span>
              <span className="block text-[10px] font-semibold uppercase tracking-wider text-brand-dark">{label}</span>
              {r.text}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
