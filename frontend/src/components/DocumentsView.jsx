import React, { useMemo } from "react";
import { FileText, FileSignature, ChevronRight, Upload } from "lucide-react";

/**
 * Lists analyzed documents grouped by filename, derived from the /history
 * audit trail. Reused for both Contracts (field="msa_filename") and
 * SOWs (field="sow_filename"). Clicking a document opens its latest analysis.
 */
const DocumentsView = ({ history, field, kind, onOpen, onNew }) => {
  const docs = useMemo(() => {
    const map = new Map();
    history.forEach((run) => {
      const name = run[field];
      if (!name) return;
      const entry = map.get(name) || { name, runs: 0, latest: run, totalRisks: 0 };
      entry.runs += 1;
      entry.totalRisks += run.total_risks || 0;
      // history is newest-first, so the first seen run is the latest.
      if (!map.has(name)) entry.latest = run;
      map.set(name, entry);
    });
    return [...map.values()].sort(
      (a, b) => new Date(b.latest.timestamp) - new Date(a.latest.timestamp)
    );
  }, [history, field]);

  const Icon = kind === "SOW" ? FileSignature : FileText;
  const chip = kind === "SOW" ? "chip-sow" : "chip-msa";

  return (
    <div className="p-6 max-w-[1400px] animate-fade-up">
      <div className="glass-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-white font-['Outfit'] flex items-center gap-2">
            <Icon className="w-4 h-4 text-indigo-400" />
            {kind === "SOW" ? "Statements of Work" : "Master Service Agreements"}
          </h3>
          <button onClick={onNew} className="btn-glass px-3 py-1.5 text-[11px] flex items-center gap-1.5">
            <Upload className="w-3.5 h-3.5" /> Analyze New
          </button>
        </div>

        {docs.length === 0 ? (
          <p className="text-[12px] text-slate-500 py-10 text-center">
            No {kind} documents analyzed yet. Run an audit to populate this list.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">
                  <th className="pb-2.5 font-semibold">Document</th>
                  <th className="pb-2.5 font-semibold">Audits</th>
                  <th className="pb-2.5 font-semibold">Latest Risks</th>
                  <th className="pb-2.5 font-semibold">Critical</th>
                  <th className="pb-2.5 font-semibold">Last Analyzed</th>
                  <th className="pb-2.5 font-semibold text-right">Open</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => {
                  const crit = (d.latest.critical_count || 0) + (d.latest.blocker_count || 0);
                  return (
                    <tr key={d.name} className="findings-row cursor-pointer" onClick={() => onOpen(d.latest.id)}>
                      <td className="py-3.5 pr-4">
                        <div className="flex items-center gap-2.5">
                          <span className={`clause-chip ${chip}`}>{kind}</span>
                          <span className="text-[12px] font-semibold text-slate-200 truncate max-w-[360px]">{d.name}</span>
                        </div>
                      </td>
                      <td className="py-3.5 text-[12px] text-slate-400">{d.runs}</td>
                      <td className="py-3.5"><span className="text-rose-400 font-bold text-[12px]">{d.latest.total_risks ?? 0}</span></td>
                      <td className="py-3.5">
                        {crit > 0
                          ? <span className="severity-pill sev-critical">{crit}</span>
                          : <span className="text-[12px] text-slate-600">0</span>}
                      </td>
                      <td className="py-3.5 text-[11px] text-slate-500">{new Date(d.latest.timestamp).toLocaleString()}</td>
                      <td className="py-3.5 text-right">
                        <ChevronRight className="w-4 h-4 text-slate-500 inline-block" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentsView;
