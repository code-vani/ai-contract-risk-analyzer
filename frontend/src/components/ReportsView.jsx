import React, { useMemo } from "react";
import { BarChart3, Download, FileJson, Printer, TrendingUp, FileWarning } from "lucide-react";

const SEVS = ["CRITICAL", "BLOCKER", "HIGH", "MEDIUM", "LOW"];
const sevClass = (s) =>
  ({ CRITICAL: "sev-critical", BLOCKER: "sev-blocker", HIGH: "sev-high", MEDIUM: "sev-medium", LOW: "sev-low" }[s] || "sev-high");
const typeLabel = (t) =>
  ({ CONTRADICTION: "Contradiction", OVERRIDE: "Override", CIRCULAR_REFERENCE: "Circular Loop", MISSING_DOCUMENT: "Missing Doc" }[t] || t);

const KPI = ({ label, value, sub, icon: Icon, accent }) => (
  <div className={`stat-card ${accent}`}>
    <div className="flex items-start justify-between">
      <div>
        <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1.5">{label}</p>
        <p className="stat-value text-3xl text-white">{value}</p>
        {sub && <p className="text-[10px] text-slate-500 mt-1.5">{sub}</p>}
      </div>
      <Icon className={`w-5 h-5 ${accent === "indigo" ? "text-indigo-400" : accent === "rose" ? "text-rose-400" : accent === "teal" ? "text-teal-400" : "text-amber-400"}`} />
    </div>
  </div>
);

const ReportsView = ({ history, allRisks, activeAnalysisName, onExportJson }) => {
  const totals = useMemo(() => {
    const analyses = history.length;
    const cumRisks = history.reduce((s, r) => s + (r.total_risks || 0), 0);
    const cumCrit = history.reduce((s, r) => s + (r.blocker_count || 0) + (r.critical_count || 0), 0);
    const avg = analyses ? Math.round(cumRisks / analyses) : 0;
    return { analyses, cumRisks, cumCrit, avg };
  }, [history]);

  const bySeverity = useMemo(() => {
    const acc = Object.fromEntries(SEVS.map((s) => [s, 0]));
    allRisks.forEach((r) => { if (acc[r.severity] != null) acc[r.severity]++; });
    return acc;
  }, [allRisks]);
  const maxSev = Math.max(1, ...Object.values(bySeverity));

  const byType = useMemo(() => {
    const acc = {};
    allRisks.forEach((r) => { acc[r.type] = (acc[r.type] || 0) + 1; });
    return acc;
  }, [allRisks]);

  const topDocs = useMemo(() => {
    return [...history].sort((a, b) => (b.total_risks || 0) - (a.total_risks || 0)).slice(0, 6);
  }, [history]);

  const exportCsv = () => {
    const rows = [["risk_id", "type", "severity", "clause_a", "clause_b", "description", "change_summary"]];
    allRisks.forEach((r) => rows.push([
      r.risk_id, r.type, r.severity, r.clause_a_section || "", r.clause_b_section || "",
      (r.description || "").replace(/"/g, '""'), (r.change_summary || "").replace(/"/g, '""'),
    ]));
    const csv = rows.map((row) => row.map((c) => `"${c ?? ""}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `techm-findings-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 space-y-4 max-w-[1500px] animate-fade-up">
      {/* Header + export */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-white font-['Outfit'] flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-indigo-400" /> Analytics &amp; Reports
          </h3>
          <p className="text-[11px] text-slate-500 mt-0.5">Current: {activeAnalysisName}</p>
        </div>
        <div className="flex items-center gap-2 no-print">
          <button onClick={exportCsv} className="btn-glass px-3 py-2 text-[11px] flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> CSV</button>
          <button onClick={onExportJson} disabled={!onExportJson} className="btn-glass px-3 py-2 text-[11px] flex items-center gap-1.5"><FileJson className="w-3.5 h-3.5" /> JSON</button>
          <button onClick={() => window.print()} className="btn-glass px-3 py-2 text-[11px] flex items-center gap-1.5"><Printer className="w-3.5 h-3.5" /> Print / PDF</button>
        </div>
      </div>

      {/* KPI row (cumulative across all audits) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPI label="Total Audits" value={totals.analyses} sub="Stored in audit trail" icon={BarChart3} accent="indigo" />
        <KPI label="Cumulative Risks" value={totals.cumRisks} sub="Across all audits" icon={TrendingUp} accent="rose" />
        <KPI label="Critical / Blocker" value={totals.cumCrit} sub="All-time" icon={FileWarning} accent="amber" />
        <KPI label="Avg Risks / Audit" value={totals.avg} sub="Mean per document pair" icon={TrendingUp} accent="teal" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Severity distribution (current analysis) */}
        <div className="glass-card p-5">
          <h4 className="text-sm font-bold text-white font-['Outfit'] mb-4">Severity Distribution — Current Audit</h4>
          <div className="space-y-2.5">
            {SEVS.map((s) => (
              <div key={s} className="flex items-center gap-3">
                <span className={`severity-pill ${sevClass(s)} w-24 justify-center`}>{s}</span>
                <div className="flex-1 h-2.5 rounded-full bg-slate-800/60 overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${(bySeverity[s] / maxSev) * 100}%`, background: "linear-gradient(90deg,#818cf8,#6366f1)" }} />
                </div>
                <span className="text-[12px] font-bold text-slate-300 w-6 text-right">{bySeverity[s]}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Risk type breakdown (current analysis) */}
        <div className="glass-card p-5">
          <h4 className="text-sm font-bold text-white font-['Outfit'] mb-4">Conflict Types — Current Audit</h4>
          {Object.keys(byType).length === 0 ? (
            <p className="text-[12px] text-slate-500 py-8 text-center">No conflicts in the current audit.</p>
          ) : (
            <div className="grid grid-cols-2 gap-2.5">
              {Object.entries(byType).sort((a, b) => b[1] - a[1]).map(([t, n]) => (
                <div key={t} className="heat-cell flex-col gap-1.5">
                  <span className="text-xl font-bold font-['Outfit'] text-slate-200">{n}</span>
                  <span className="uppercase text-[9px] text-slate-400">{typeLabel(t)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Most-flagged documents */}
      <div className="glass-card p-5">
        <h4 className="text-sm font-bold text-white font-['Outfit'] mb-3">Most-Flagged Audits</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">
                <th className="pb-2 font-semibold">Document Pair</th>
                <th className="pb-2 font-semibold">Total Risks</th>
                <th className="pb-2 font-semibold">Critical</th>
                <th className="pb-2 font-semibold">Date</th>
              </tr>
            </thead>
            <tbody>
              {topDocs.map((r) => (
                <tr key={r.id} className="findings-row">
                  <td className="py-3 text-[12px] text-slate-300 truncate max-w-[360px]">{r.msa_filename} &amp; {r.sow_filename}</td>
                  <td className="py-3"><span className="text-rose-400 font-bold text-[12px]">{r.total_risks}</span></td>
                  <td className="py-3 text-[12px] text-slate-400">{r.blocker_count || 0}</td>
                  <td className="py-3 text-[11px] text-slate-500">{new Date(r.timestamp).toLocaleDateString()}</td>
                </tr>
              ))}
              {topDocs.length === 0 && (
                <tr><td colSpan="4" className="py-8 text-center text-[12px] text-slate-500">No audits recorded yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ReportsView;
