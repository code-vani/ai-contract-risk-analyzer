import React from "react";
import { AlertTriangle, X, ShieldAlert, FileWarning, CheckCircle2 } from "lucide-react";
import InlineDiff from "./InlineDiff";

const GraphSidePanel = ({ clause, onClose, risk = null }) => {
  if (!clause) return null;

  const getSeverityBadge = (severity) => {
    switch (severity) {
      case "CRITICAL":
        return "badge-critical";
      case "BLOCKER":
        return "badge-blocker";
      case "HIGH":
        return "badge-high";
      default:
        return "badge-high";
    }
  };

  const getTypeLabel = (type) => {
    switch (type) {
      case "CONTRADICTION": return "Contradiction";
      case "OVERRIDE": return "Override";
      case "CIRCULAR_REFERENCE": return "Circular Loop";
      case "MISSING_DOCUMENT": return "Missing Doc";
      default: return type;
    }
  };

  const renderRedline = () => {
    if (!risk) return null;
    const original = risk.original_text || clause.text || "";
    const suggested = risk.suggested_text || "";
    const normalise = (s) => s.replace(/\s+/g, " ").trim();
    if (!suggested || normalise(suggested) === normalise(original)) return null;

    return (
      <div className="space-y-2" style={{ animationDelay: '0.2s' }}>
        <InlineDiff originalText={original} suggestedText={suggested} />

        {risk.change_summary && (
          <div className="flex items-start gap-2 p-2.5 rounded-lg" style={{ background: 'rgba(99,102,241,0.05)', border: '1px solid rgba(99,102,241,0.1)' }}>
            <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
            <p className="text-[10px] text-slate-400 leading-relaxed">
              {risk.change_summary}
            </p>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col w-full text-slate-200 side-panel-enter">
      
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="p-4 border-b border-slate-800/50 flex items-start justify-between" style={{ background: 'linear-gradient(180deg, rgba(15,23,42,0.4), transparent)' }}>
        <div className="space-y-1.5 min-w-0 flex-1">
          <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${
            clause.document_type === "MSA"
              ? "text-indigo-300"
              : "text-teal-300"
          }`} style={{
            background: clause.document_type === "MSA" ? 'rgba(99,102,241,0.1)' : 'rgba(13,148,136,0.1)',
            border: `1px solid ${clause.document_type === "MSA" ? 'rgba(99,102,241,0.2)' : 'rgba(13,148,136,0.2)'}`,
          }}>
            {clause.document_type} § {clause.section_number || clause.id?.replace(/^[^-]+-/, "")}
          </span>
          <h2 className="text-base font-bold text-white line-clamp-2 font-['Outfit']">{clause.title}</h2>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 hover:bg-slate-800/60 rounded-lg text-slate-500 hover:text-white transition-all shrink-0 ml-2"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* ── Content ────────────────────────────────────────────────────── */}
      <div className="p-4 flex-1 overflow-y-auto space-y-4">
        
        {/* Risk Banner */}
        {risk && (
          <div className="rounded-xl overflow-hidden animate-fade-up" style={{ animationDelay: '0.05s' }}>
            <div className="p-3.5 space-y-2" style={{
              background: risk.severity === "CRITICAL" || risk.severity === "BLOCKER"
                ? 'linear-gradient(135deg, rgba(239,68,68,0.08), rgba(239,68,68,0.02))'
                : 'linear-gradient(135deg, rgba(244,63,94,0.08), rgba(244,63,94,0.02))',
              border: `1px solid ${risk.severity === "CRITICAL" || risk.severity === "BLOCKER" ? 'rgba(239,68,68,0.15)' : 'rgba(244,63,94,0.15)'}`,
              borderRadius: '12px',
            }}>
              <div className="flex items-center gap-2">
                {risk.severity === "CRITICAL" || risk.severity === "BLOCKER" ? (
                  <ShieldAlert className="w-4 h-4 shrink-0 text-red-400" />
                ) : (
                  <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                )}
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${getSeverityBadge(risk.severity)}`}>
                    {risk.severity}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">{risk.risk_id}</span>
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold text-slate-400" style={{ background: 'rgba(148,163,184,0.06)', border: '1px solid rgba(148,163,184,0.1)' }}>
                    {getTypeLabel(risk.type)}
                  </span>
                </div>
              </div>
              <p className="text-[11px] text-slate-300 leading-relaxed">
                {risk.description}
              </p>
              {risk.which_wins && (
                <p className="text-[10px] text-slate-500 italic leading-relaxed">
                  <strong className="text-slate-400">Resolution:</strong> {risk.which_wins}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Clause Meta */}
        <div className="grid grid-cols-2 gap-2 animate-fade-up" style={{ animationDelay: '0.1s' }}>
          <div className="p-2.5 rounded-lg" style={{ background: 'rgba(15,23,42,0.4)', border: '1px solid rgba(148,163,184,0.06)' }}>
            <span className="text-[9px] text-slate-600 block uppercase font-bold tracking-wider">Category</span>
            <span className="text-[12px] font-semibold text-slate-300 capitalize mt-0.5 block">{clause.clause_type || "General"}</span>
          </div>
          <div className="p-2.5 rounded-lg" style={{ background: 'rgba(15,23,42,0.4)', border: '1px solid rgba(148,163,184,0.06)' }}>
            <span className="text-[9px] text-slate-600 block uppercase font-bold tracking-wider">Document</span>
            <span className="text-[12px] font-semibold text-slate-300 mt-0.5 block">{clause.document_type}</span>
          </div>
        </div>

        {/* Original Clause Text */}
        <div className="space-y-1.5 animate-fade-up" style={{ animationDelay: '0.15s' }}>
          <span className="text-[10px] text-slate-500 block font-bold uppercase tracking-wider">Clause Text</span>
          <div className="p-3.5 rounded-xl max-h-40 overflow-y-auto" style={{ background: 'rgba(6,9,17,0.6)', border: '1px solid rgba(148,163,184,0.06)' }}>
            <p className="text-[11px] text-slate-300 leading-relaxed whitespace-pre-wrap">
              {clause.text}
            </p>
          </div>
        </div>

        {/* Redline */}
        {renderRedline()}

        {/* Financial clause — figures need human expertise, not AI rewrite */}
        {risk && risk.type === "FINANCIAL_CLAUSE" && (
          <div className="flex items-start gap-2 p-2.5 rounded-lg" style={{ background: 'rgba(245,158,11,0.05)', border: '1px solid rgba(245,158,11,0.15)' }}>
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-[10px] text-amber-300 font-semibold">Manual review required</p>
              <p className="text-[10px] text-slate-500 leading-relaxed mt-0.5">
                Verify financial figures (amounts, %, SLA thresholds) against the MSA — AI cannot determine the correct values.
              </p>
            </div>
          </div>
        )}

        {/* No redline fallback — show when a risk exists but no suggestion was generated */}
        {risk && risk.type !== "MISSING_DOCUMENT" && risk.type !== "FINANCIAL_CLAUSE" && !risk.suggested_text && (
          <div className="flex items-start gap-2 p-2.5 rounded-lg" style={{ background: 'rgba(148,163,184,0.04)', border: '1px solid rgba(148,163,184,0.08)' }}>
            <AlertTriangle className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
            <p className="text-[10px] text-slate-500 leading-relaxed">
              No AI redline available for this finding — manual review required.
            </p>
          </div>
        )}

        {/* Missing doc special case */}
        {risk && risk.type === "MISSING_DOCUMENT" && (
          <div className="flex items-start gap-2.5 p-3 rounded-xl animate-fade-up" style={{ animationDelay: '0.25s', background: 'rgba(249,115,22,0.06)', border: '1px solid rgba(249,115,22,0.12)' }}>
            <FileWarning className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-[11px] text-amber-300 font-bold">Action Required</p>
              <p className="text-[10px] text-slate-400 leading-relaxed mt-0.5">{risk.change_summary}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GraphSidePanel;
