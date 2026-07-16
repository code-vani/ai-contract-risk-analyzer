import React from "react";
import { SlidersHorizontal } from "lucide-react";

const Toggle = ({ label, description, checked, onChange, onColor = "#2563EB" }) => (
  <div
    onClick={() => onChange(!checked)}
    style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, cursor: "pointer", padding: "5px 0", userSelect: "none" }}
  >
    <div>
      <div style={{ fontSize: 12.5, fontWeight: 600, color: checked ? "#E2E8F0" : "#64748B", transition: "color 0.15s" }}>{label}</div>
      <div style={{ fontSize: 10.5, color: "#475569", marginTop: 1 }}>{description}</div>
    </div>
    <div style={{
      width: 38, height: 22, borderRadius: 99, position: "relative", flexShrink: 0,
      background: checked ? onColor : "#1E293B",
      border: `1px solid ${checked ? onColor : "#334155"}`,
      transition: "background 0.2s ease, border-color 0.2s ease",
    }}>
      <div style={{
        width: 18, height: 18, borderRadius: "50%", background: "white",
        position: "absolute", top: 1,
        left: checked ? 17 : 1,
        transition: "left 0.22s cubic-bezier(0.34,1.56,0.64,1)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.35)",
      }} />
    </div>
  </div>
);

const GraphControls = ({ filters, onChange }) => {
  const set = (key, val) => onChange({ ...filters, [key]: val });
  return (
    <div style={{ background: "rgba(30,41,59,0.6)", border: "1px solid #1E293B", borderRadius: 10, padding: "14px 14px 10px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10, fontWeight: 700, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 10 }}>
        <SlidersHorizontal style={{ width: 12, height: 12 }} /> Display Filters
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <Toggle label="MSA Clauses"  description="Master Agreement nodes"    checked={filters.showMsa}       onChange={(v) => set("showMsa", v)}       onColor="#6366F1" />
        <div style={{ borderTop: "1px solid #1E293B", margin: "4px 0" }} />
        <Toggle label="SOW Clauses"  description="Statement of Work nodes"   checked={filters.showSow}       onChange={(v) => set("showSow", v)}       onColor="#0D9488" />
        <div style={{ borderTop: "1px solid #1E293B", margin: "4px 0" }} />
        <Toggle label="Risks Only"   description="Isolate flagged conflicts"  checked={filters.showRisksOnly} onChange={(v) => set("showRisksOnly", v)} onColor="#DC2626" />
      </div>
    </div>
  );
};

export default GraphControls;
