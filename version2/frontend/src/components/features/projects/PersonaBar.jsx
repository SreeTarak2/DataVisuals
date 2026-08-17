import React from "react";
import { Compass, Briefcase, Microscope, Megaphone, Cog } from "lucide-react";
import { cn } from "../../../lib/utils";
import usePersonaStore from "../../../store/personaStore";

/* ═══════════════════════════════════════════════════════════════
   PersonaBar — "same dataset, different audience → different
   dashboard". One-click persona switcher. Switching re-ranks which
   KPIs get selected (server-side) so the dashboard matches the
   audience: CEO → revenue/risk; Analyst → statistics; etc.
   ═══════════════════════════════════════════════════════════════ */

export const PERSONA_OPTIONS = [
  { key: "explorer", label: "Explorer", icon: Compass, title: "Neutral default — broad discovery" },
  { key: "ceo", label: "CEO", icon: Briefcase, title: "Executive view — revenue, growth, risks" },
  { key: "analyst", label: "Analyst", icon: Microscope, title: "Statistical depth — distributions, outliers" },
  { key: "marketing", label: "Marketing", icon: Megaphone, title: "Acquisition, campaigns, segments" },
  { key: "ops", label: "Operations", icon: Cog, title: "Efficiency, volume, quality" },
];

function PersonaBar({ datasetId }) {
  const persona = usePersonaStore((s) => s.personas[datasetId] || "explorer");
  const setPersona = usePersonaStore((s) => s.setPersona);

  if (!datasetId) return null;

  return (
    <div className="flex items-center gap-1 shrink-0" title="Who is this dashboard for?">
      {PERSONA_OPTIONS.map(({ key, label, icon: Icon, title }) => {
        const active = persona === key;
        return (
          <button
            key={key}
            type="button"
            onClick={() => setPersona(datasetId, key)}
            title={title}
            className={cn(
              "flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold border transition-all",
              active
                ? "bg-accent-primary/10 text-accent-primary border-accent-primary/30"
                : "text-muted border-border/50 hover:text-secondary hover:border-border"
            )}
          >
            <Icon size={12} />
            {label}
          </button>
        );
      })}
    </div>
  );
}

export default PersonaBar;
