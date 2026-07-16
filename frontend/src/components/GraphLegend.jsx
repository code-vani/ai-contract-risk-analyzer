import React from "react";
import { Map } from "lucide-react";

const LegendItem = ({ color, border, label, type = "node" }) => (
  <div className="flex items-center gap-2.5 group">
    {type === "node" ? (
      <span
        className="w-4 h-4 rounded-md shrink-0 transition-transform group-hover:scale-110"
        style={{ background: color, border: `1.5px solid ${border}`, boxShadow: `0 0 8px ${color}30` }}
      />
    ) : (
      <div className="w-8 flex items-center justify-center shrink-0">
        <div className={`w-full ${type}`} style={{ borderColor: color, background: type === 'line-solid' ? color : undefined }} />
      </div>
    )}
    <span className="text-[11px] text-slate-400 group-hover:text-slate-200 transition-colors">{label}</span>
  </div>
);

const GraphLegend = () => {
  return (
    <div className="glass-card p-4 text-xs space-y-3 text-slate-300 animate-fade-up" style={{ animationDelay: '0.1s' }}>
      <h3 className="font-bold text-white uppercase tracking-widest text-[10px] font-['Outfit'] flex items-center gap-1.5">
        <Map className="w-3.5 h-3.5 text-indigo-400" /> Graph Legend
      </h3>

      {/* Node Types */}
      <div className="space-y-2">
        <span className="text-[9px] text-slate-600 block uppercase font-bold tracking-wider">Nodes</span>
        <div className="grid grid-cols-1 gap-1.5">
          <LegendItem color="#6366f1" border="#4f46e5" label="MSA Clause" />
          <LegendItem color="#0d9488" border="#0f766e" label="SOW Clause" />
          <LegendItem color="#6366f1" border="#f43f5e" label="Flagged (red ring)" />
        </div>
      </div>

      <div className="border-t border-slate-800/40" />

      {/* Edge Types */}
      <div className="space-y-2">
        <span className="text-[9px] text-slate-600 block uppercase font-bold tracking-wider">Connections</span>
        <div className="space-y-2">
          <div className="flex items-center gap-2.5">
            <div className="w-8 flex items-center shrink-0">
              <div className="w-full h-[2px] rounded-full" style={{ background: '#6366f1' }} />
            </div>
            <span className="text-[11px] text-slate-400">MSA → MSA Link</span>
          </div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 flex items-center shrink-0">
              <div className="w-full h-[2px] rounded-full" style={{ background: '#0d9488' }} />
            </div>
            <span className="text-[11px] text-slate-400">SOW → SOW Link</span>
          </div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 flex items-center shrink-0">
              <div className="w-full h-0 border-t-[1.5px] border-dashed" style={{ borderColor: '#64748b' }} />
            </div>
            <span className="text-[11px] text-slate-400">Cross-Doc Reference</span>
          </div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 flex items-center shrink-0">
              <div className="w-full h-0 border-t-[2.5px] border-dashed border-rose-500" />
            </div>
            <span className="text-[11px] text-slate-400">Contradiction</span>
          </div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 flex items-center shrink-0">
              <div className="w-full h-0 border-t-[2.5px] border-dashed" style={{ borderColor: '#f59e0b' }} />
            </div>
            <span className="text-[11px] text-slate-400">Override</span>
          </div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 flex items-center shrink-0">
              <div className="w-full h-0 border-t-[3px] border-dotted border-red-700" />
            </div>
            <span className="text-[11px] text-slate-400">Circular Loop</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GraphLegend;
