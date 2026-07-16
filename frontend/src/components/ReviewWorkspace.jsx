import React, { useMemo, useState, useEffect } from "react";
import { Wand2, Copy, Check, FileText, Sparkles, AlertTriangle, ClipboardCheck } from "lucide-react";
import InlineDiff from "./InlineDiff";

const SEV_ORDER = { CRITICAL: 0, BLOCKER: 1, HIGH: 2, MEDIUM: 3, LOW: 4 };
const sevClass = (s) =>
  ({ CRITICAL: "sev-critical", BLOCKER: "sev-blocker", HIGH: "sev-high", MEDIUM: "sev-medium", LOW: "sev-low" }[s] || "sev-high");
const typeLabel = (t) =>
  ({ CONTRADICTION: "Contradiction", OVERRIDE: "Override", CIRCULAR_REFERENCE: "Circular Loop", MISSING_DOCUMENT: "Missing Doc" }[t] || t);

/**
 * Contract Review Workspace — the AI Redlines view.
 * Left: risky clauses (severity-ordered). Center: clause text with inline
 * redline. Right: AI suggestion with Copy / Apply. Data comes from the loaded
 * analysis (nodes + risks); nothing new is fetched.
 */
const ReviewWorkspace = ({ nodes, risks, allRisks, initialSection, backendUrl }) => {
  // One review item per risk that carries a redline (or any risk as fallback).
  const items = useMemo(() => {
    const seen = new Set();
    const out = [];
    [...allRisks]
      .sort((a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9))
      .forEach((r) => {
        const section = r.clause_b_section || r.clause_a_section;
        if (!section || seen.has(section)) return; // one review card per clause
        seen.add(section);
        const node = nodes.find((n) => n.id === section);
        out.push({ section, risk: r, node, title: node?.title || typeLabel(r.type) });
      });
    return out;
  }, [allRisks, nodes]);

  const [selected, setSelected] = useState(initialSection || items[0]?.section || null);
  // Set of accepted risk DB ids, seeded from the persisted `decision` field.
  const [applied, setApplied] = useState(() => new Set());
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (initialSection) setSelected(initialSection);
  }, [initialSection]);
  useEffect(() => {
    if (!selected && items[0]) setSelected(items[0].section);
  }, [items, selected]);

  // Seed accepted-state from the backend's persisted decisions whenever the
  // analysis (its risk list) changes.
  useEffect(() => {
    const accepted = new Set();
    allRisks.forEach((r) => { if (r.decision === "ACCEPTED" && r.id != null) accepted.add(r.id); });
    setApplied(accepted);
  }, [allRisks]);

  const active = items.find((i) => i.section === selected) || null;
  const risk = active?.risk || (selected ? risks[selected] : null);
  const node = active?.node || nodes.find((n) => n.id === selected);
  const original = risk?.original_text || node?.text || "";
  const suggested = risk?.suggested_text || "";
  // Collapse all whitespace (newlines, double-spaces, etc.) before comparing so that
  // the backend fallback — which returns suggested_text = original_text verbatim,
  // including paragraph breaks — is correctly detected as "no real change".
  const normalise = (s) => s.replace(/\s+/g, " ").trim();
  const hasDiff = normalise(suggested) !== "" && normalise(suggested) !== normalise(original);

  const copySuggestion = async () => {
    if (!hasDiff) return;
    try { await navigator.clipboard.writeText(suggested); } catch { /* clipboard unavailable */ }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  const toggleApplied = async () => {
    if (!risk || risk.id == null) return;
    const isAccepted = applied.has(risk.id);
    const nextDecision = isAccepted ? null : "ACCEPTED";
    // Optimistic local update.
    setApplied((prev) => {
      const next = new Set(prev);
      if (isAccepted) next.delete(risk.id);
      else next.add(risk.id);
      return next;
    });
    if (!backendUrl) return; // no backend configured — keep it local only
    setSaving(true);
    try {
      const res = await fetch(`${backendUrl}/risks/${risk.id}/decision`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: nextDecision }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      risk.decision = nextDecision; // keep the in-memory record in sync
    } catch {
      // Roll back on failure so the UI reflects reality.
      setApplied((prev) => {
        const next = new Set(prev);
        if (isAccepted) next.add(risk.id);
        else next.delete(risk.id);
        return next;
      });
    } finally {
      setSaving(false);
    }
  };

  if (items.length === 0) {
    return (
      <div className="p-6 h-full flex items-center justify-center animate-fade-up">
        <div className="glass-card p-10 max-w-md text-center flex flex-col items-center gap-4">
          <div className="p-4 rounded-2xl" style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.1), rgba(13,148,136,0.08))", border: "1px solid rgba(99,102,241,0.15)" }}>
            <Wand2 className="w-8 h-8 text-indigo-400" />
          </div>
          <h3 className="text-lg font-bold text-white font-['Outfit']">No redlines to review</h3>
          <p className="text-[12px] text-slate-500 leading-relaxed">
            Run or open an analysis with detected conflicts to see AI-suggested redlines here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 p-6 xl:h-full min-h-0">
      {/* Left: clause list */}
      <div className="xl:col-span-3 glass-card p-3 flex flex-col min-h-[240px] xl:min-h-0">
        <h3 className="text-[11px] font-bold text-white uppercase tracking-widest px-1.5 py-1.5 flex items-center gap-1.5 font-['Outfit']">
          <ClipboardCheck className="w-3.5 h-3.5 text-indigo-400" /> Flagged Clauses ({items.length})
        </h3>
        <div className="flex-1 overflow-y-auto mt-1 space-y-1 pr-1">
          {items.map((it) => (
            <button
              key={it.section}
              onClick={() => setSelected(it.section)}
              className={`w-full text-left p-2.5 rounded-lg border transition-all ${
                selected === it.section
                  ? "bg-indigo-500/10 border-indigo-500/30"
                  : "bg-slate-950/30 border-transparent hover:border-slate-800"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`severity-pill ${sevClass(it.risk.severity)} !py-0.5 !px-1.5 !text-[9px]`}>{it.risk.severity}</span>
                <span className={`clause-chip ${it.section?.startsWith("MSA") ? "chip-msa" : "chip-sow"}`}>{it.section}</span>
                {applied.has(it.risk.id) && <Check className="w-3 h-3 text-emerald-400 ml-auto" />}
              </div>
              <p className="text-[11px] font-semibold text-slate-200 truncate">{it.title}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Center: document reader with redline */}
      <div className="xl:col-span-6 glass-card p-5 flex flex-col min-h-[340px] xl:min-h-0">
        <div className="flex items-center gap-2 mb-3">
          <FileText className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-bold text-white font-['Outfit']">{node?.title || typeLabel(risk?.type)}</h3>
          <span className={`clause-chip ${selected?.startsWith("MSA") ? "chip-msa" : "chip-sow"} ml-auto`}>{selected}</span>
        </div>
        <div className="flex-1 overflow-y-auto space-y-4">
          <div>
            <span className="text-[10px] text-slate-500 block font-bold uppercase tracking-wider mb-1.5">Original Clause</span>
            <div className="doc-reader">{original || <em className="text-slate-600">No source text available.</em>}</div>
          </div>
          <div>
            <span className="text-[10px] text-slate-500 block font-bold uppercase tracking-wider mb-1.5">Redline (proposed change)</span>
            {hasDiff ? (
              <InlineDiff originalText={original} suggestedText={suggested} />
            ) : risk?.type === "FINANCIAL_CLAUSE" ? (
              <div className="flex items-start gap-2.5 p-3 rounded-lg" style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.18)" }}>
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-400" />
                <div>
                  <p className="text-[11px] text-amber-300 font-semibold leading-snug">Manual review required for financial figures</p>
                  <p className="text-[10px] text-slate-500 leading-relaxed mt-0.5">
                    AI cannot determine the correct dollar amounts, percentages, or SLA thresholds. Verify these figures manually against the MSA.
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-2.5 p-3 rounded-lg" style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.18)" }}>
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-400" />
                <div>
                  <p className="text-[11px] text-amber-300 font-semibold leading-snug">No AI redline generated</p>
                  <p className="text-[10px] text-slate-500 leading-relaxed mt-0.5">
                    Gemini was unavailable or rate-limited during analysis. Run a new audit to generate word-level suggestions.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Right: AI suggestion + actions */}
      <div className="xl:col-span-3 glass-card p-4 flex flex-col min-h-[280px] xl:min-h-0">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-bold text-white font-['Outfit']">AI Suggestion</h3>
        </div>
        {risk ? (
          <div className="flex-1 overflow-y-auto space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`severity-pill ${sevClass(risk.severity)}`}>{risk.severity}</span>
              <span className="clause-chip chip-msa">{typeLabel(risk.type)}</span>
              {risk.confidence != null && (
                <span className="text-[10px] text-slate-500 font-mono">conf {Math.round((risk.confidence <= 1 ? risk.confidence * 100 : risk.confidence))}%</span>
              )}
            </div>
            <p className="text-[11px] text-slate-300 leading-relaxed">{risk.description}</p>
            {risk.which_wins && (
              <div className="p-2.5 rounded-lg" style={{ background: "rgba(13,148,136,0.06)", border: "1px solid rgba(13,148,136,0.15)" }}>
                <span className="text-[9px] text-teal-400 uppercase font-bold tracking-wider block mb-1">Resolution</span>
                <p className="text-[10px] text-slate-400 leading-relaxed">{risk.which_wins}</p>
              </div>
            )}
            {risk.change_summary && (
              <div className="p-2.5 rounded-lg" style={{ background: "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.1)" }}>
                <span className="text-[9px] text-indigo-300 uppercase font-bold tracking-wider block mb-1">Change Summary</span>
                <p className="text-[10px] text-slate-400 leading-relaxed">{risk.change_summary}</p>
              </div>
            )}
          </div>
        ) : (
          <p className="text-[11px] text-slate-500 flex-1">Select a clause to view its suggestion.</p>
        )}
        {hasDiff && (
          <div className="flex gap-2 pt-3 mt-3 border-t border-slate-800/50">
            <button onClick={copySuggestion} className="btn-glass flex-1 py-2 text-[11px] flex items-center justify-center gap-1.5">
              {copied ? <><Check className="w-3.5 h-3.5" /> Copied</> : <><Copy className="w-3.5 h-3.5" /> Copy</>}
            </button>
            <button
              onClick={toggleApplied}
              disabled={saving}
              title="Mark this redline as accepted (saved to the analysis — does not edit the source document)"
              className={`flex-1 py-2 text-[11px] rounded-lg font-semibold flex items-center justify-center gap-1.5 transition-all disabled:opacity-60 ${
                risk && applied.has(risk.id)
                  ? "bg-emerald-600/20 border border-emerald-500/40 text-emerald-300"
                  : "btn-primary-cta"
              }`}
            >
              {saving
                ? <><div className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" /> Saving…</>
                : risk && applied.has(risk.id)
                  ? <><Check className="w-3.5 h-3.5" /> Accepted</>
                  : "Accept Redline"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReviewWorkspace;
