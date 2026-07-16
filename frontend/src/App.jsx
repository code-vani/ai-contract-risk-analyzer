import React, { useState, useMemo, useEffect, useRef, lazy, Suspense } from "react";
const ClauseGraph = lazy(() => import("./components/ClauseGraph"));
import GraphSidePanel from "./components/GraphSidePanel";
import GraphLegend from "./components/GraphLegend";
import GraphControls from "./components/GraphControls";
import CycleWarning from "./components/CycleWarning";
import DocumentsView from "./components/DocumentsView";
import ReviewWorkspace from "./components/ReviewWorkspace";
import ReportsView from "./components/ReportsView";
import SettingsModal from "./components/SettingsModal";
import {
  extractRiskList, buildRisksMap, mapNodesWithRisk,
  dedupeRisks, buildRiskEdges, computeStats, countUnmapped,
} from "./lib/analysisMapping";
import {
  GitBranch, Info, FileText, AlertTriangle, Zap, CircleDot, Maximize2, Minimize2,
  Upload, Download, CheckCircle2, LayoutDashboard, FileSignature,
  ClipboardList, Network as NetworkIcon, ShieldAlert, Wand2, BarChart3,
  History, Search, Bell, Scale, Plus, Play, X, Sparkles, TrendingUp,
  ChevronRight, RotateCcw, Settings, Shield, AlertCircle, Expand, Crosshair,
} from "lucide-react";

// ─── Mock Dataset ────────────────────────────────────────────────────────────
const MOCK_NODES = [
  { id: "MSA-1",   section_number: "1",   document_type: "MSA", title: "Definitions",          text: "This section contains definitions for intellectual property, deliverables, and service levels used throughout the agreement.", clause_type: "definitions",  has_risk: false },
  { id: "MSA-2",   section_number: "2",   document_type: "MSA", title: "Scope of Services",    text: "Vendor shall perform the services set forth in each mutually executed Statement of Work (SOW). Each SOW shall be subject to the terms of this MSA.", clause_type: "scope",        has_risk: false },
  { id: "MSA-4.1", section_number: "4.1", document_type: "MSA", title: "Payment Terms",        text: "All invoices shall be paid within thirty (30) days of invoice receipt by the Client. Late payments shall incur standard interest.", clause_type: "payment",      has_risk: true  },
  { id: "MSA-5",   section_number: "5",   document_type: "MSA", title: "Intellectual Property",text: "All work product, deliverables, and code created by the Vendor under any SOW shall be the sole and exclusive property of the Client upon payment.", clause_type: "ip",           has_risk: true  },
  { id: "MSA-7.1", section_number: "7.1", document_type: "MSA", title: "Limitation of Liability", text: "Except for breaches of confidentiality, the total aggregate liability of either party shall be capped at the total amount paid under the applicable SOW.", clause_type: "liability",    has_risk: true  },
  { id: "MSA-8.1", section_number: "8.1", document_type: "MSA", title: "Termination Notice",  text: "Either party may terminate this Master Agreement or any individual SOW for convenience by providing at least thirty (30) days written notice.", clause_type: "termination", has_risk: true  },
  { id: "SOW-1",   section_number: "1",   document_type: "SOW", title: "Project Overview",     text: "This SOW defines the scope of work for the Cloud Infrastructure Migration and API Gateway development project.", clause_type: "overview",     has_risk: false },
  { id: "SOW-2.2", section_number: "2.2", document_type: "SOW", title: "Milestone Payments",   text: "All milestone-based invoices submitted by the Vendor shall be paid by the Client within forty-five (45) days of receipt.", clause_type: "payment",      has_risk: true  },
  { id: "SOW-3.1", section_number: "3.1", document_type: "SOW", title: "Deliverables Schedule",text: "All deliverables and technical specifications are defined in Schedule 1 – Project Scope Document, which must be executed concurrently.", clause_type: "deliverables", has_risk: true  },
  { id: "SOW-5",   section_number: "5",   document_type: "SOW", title: "Late Delivery Penalties", text: "If the Vendor fails to meet key milestones, penalties and service level deductions will be calculated and applied as defined in SOW Section 9.", clause_type: "penalties",    has_risk: true  },
  { id: "SOW-6",   section_number: "6",   document_type: "SOW", title: "IP Retention",         text: "Notwithstanding MSA Section 5, all developed code, schemas, and source artifacts shall remain the property of the Vendor for a period of six (6) months post-delivery.", clause_type: "ip",           has_risk: true  },
  { id: "SOW-7",   section_number: "7",   document_type: "SOW", title: "Breach Liability Cap", text: "Notwithstanding MSA Section 7, the Vendor's liability for data breaches, cybersecurity incidents, or leakages shall be uncapped and unlimited.", clause_type: "liability",    has_risk: true  },
  { id: "SOW-8",   section_number: "8",   document_type: "SOW", title: "SOW Termination",      text: "Client may terminate this Statement of Work for convenience by giving seven (7) days written notice to the Vendor.", clause_type: "termination", has_risk: true  },
  { id: "SOW-9",   section_number: "9",   document_type: "SOW", title: "Penalty Calculations", text: "Penalty calculations and adjustments to total contract values shall refer directly to performance milestones defined in SOW Section 5.", clause_type: "penalties",    has_risk: true  },
];

const MOCK_EDGES = [
  { from: "SOW-1",   to: "MSA-2",   edge_type: "reference"       },
  { from: "SOW-6",   to: "MSA-5",   edge_type: "cross_document"  },
  { from: "SOW-7",   to: "MSA-7.1", edge_type: "cross_document"  },
  { from: "SOW-2.2", to: "MSA-4.1", edge_type: "contradiction"   },
  { from: "SOW-8",   to: "MSA-8.1", edge_type: "contradiction"   },
  { from: "SOW-5",   to: "SOW-9",   edge_type: "circular"        },
  { from: "SOW-9",   to: "SOW-5",   edge_type: "circular"        },
];

const MOCK_RISKS = {
  "SOW-2.2": { risk_id: "RISK-001", type: "CONTRADICTION",      severity: "HIGH",     clause_a_section: "MSA-4.1", clause_b_section: "SOW-2.2", description: "Payment Terms Mismatch: SOW specifies 45-day payment terms, directly contradicting MSA's strict 30-day rule.", which_wins: "MSA takes precedence (MSA Section 2) unless SOW explicitly overrides using standard waiver language.", original_text: "All milestone-based invoices shall be paid within forty-five (45) days of receipt.", suggested_text: "All milestone-based invoices shall be paid within thirty (30) days of receipt, in accordance with MSA Section 4.1.", change_summary: "Align SOW payment window to 30 days to match the governing MSA." },
  "SOW-8":   { risk_id: "RISK-002", type: "CONTRADICTION",      severity: "HIGH",     clause_a_section: "MSA-8.1", clause_b_section: "SOW-8",   description: "Notice Period Contradiction: SOW specifies 7 days termination notice vs the MSA's 30-day requirement.", which_wins: "MSA governs, creating an invalid short-notice termination clause in the SOW.", original_text: "Client may terminate this SOW for convenience by giving seven (7) days written notice.", suggested_text: "Client may terminate this SOW for convenience by giving thirty (30) days written notice, per MSA Section 8.1.", change_summary: "Increase SOW termination notice period to 30 days." },
  "SOW-6":   { risk_id: "RISK-003", type: "OVERRIDE",           severity: "HIGH",     clause_a_section: "MSA-5",   clause_b_section: "SOW-6",   description: "IP Override: SOW claims Vendor ownership of deliverables for 6 months, overriding MSA's client-ownership clause.", which_wins: "SOW explicitly overrides MSA ('Notwithstanding Section 5'). Highly risky for the Client.", original_text: "Notwithstanding MSA Section 5, all developed code shall remain the property of the Vendor for six (6) months post-delivery.", suggested_text: "All developed code shall be the sole property of the Client upon delivery, per MSA Section 5.", change_summary: "Remove vendor IP retention period to preserve client ownership." },
  "SOW-7":   { risk_id: "RISK-004", type: "OVERRIDE",           severity: "HIGH",     clause_a_section: "MSA-7.1", clause_b_section: "SOW-7",   description: "Uncapped Breach Liability: SOW makes cybersecurity breach liability uncapped, bypassing MSA's aggregate cap.", which_wins: "SOW override takes precedence, leaving Vendor exposed to unlimited breach liability.", original_text: "Notwithstanding MSA Section 7, the Vendor's liability for data breaches shall be uncapped and unlimited.", suggested_text: "Vendor's liability for data breaches shall be subject to the liability caps in MSA Section 7.1.", change_summary: "Enforce standard liability limits for cybersecurity breaches." },
  "SOW-5":   { risk_id: "RISK-005", type: "CIRCULAR_REFERENCE", severity: "CRITICAL", clause_a_section: "SOW-5",   clause_b_section: "SOW-9",   description: "Circular Drafting Loop: SOW §5 references §9 for penalties, while §9 references §5 for milestones — unresolvable.", which_wins: "Neither. Circular loops create an unenforceable clause since values cannot be resolved.", original_text: "Penalties will be calculated as defined in SOW Section 9.", suggested_text: "Penalties will be calculated as defined in SLA Exhibit A, Table B.", change_summary: "Break loop by pointing penalty calculation to an external SLA exhibit." },
  "SOW-9":   { risk_id: "RISK-006", type: "CIRCULAR_REFERENCE", severity: "CRITICAL", clause_a_section: "SOW-9",   clause_b_section: "SOW-5",   description: "Circular Drafting Loop: SOW §9 refers to §5 for criteria, closing the reference loop — unresolvable.", which_wins: "Unresolvable loop. Self-referencing loop voids enforcement.", original_text: "Penalty calculations shall refer to performance milestones defined in SOW Section 5.", suggested_text: "Penalty calculations shall refer to performance milestones in the project timeline schedule.", change_summary: "Break circularity by referencing a linear timeline schedule." },
  "SOW-3.1": { risk_id: "RISK-007", type: "MISSING_DOCUMENT",   severity: "BLOCKER",  clause_a_section: "SOW-3.1", clause_b_section: null,       description: "Missing Document: SOW references 'Schedule 1 – Project Scope Document' which was not uploaded.", which_wins: null, original_text: "All deliverables are defined in Schedule 1 – Project Scope Document.", suggested_text: null, change_summary: "ACTION REQUIRED: Upload 'Schedule 1 – Project Scope Document' to complete analysis." },
};

const MOCK_CYCLES = [
  { cycle_path: ["SOW-5", "SOW-9", "SOW-5"], severity: "CRITICAL", description: "Self-referential loop: Penalty (SOW §9) and Late penalties (SOW §5) point recursively to each other." },
];

const BACKEND_URL =
  (typeof localStorage !== "undefined" && localStorage.getItem("backendUrl")) ||
  import.meta.env.VITE_BACKEND_URL ||
  "http://localhost:8000";

// ─── Navigation ──────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard",    icon: LayoutDashboard },
  { id: "risks",     label: "Risk Center",  icon: ShieldAlert,    badgeKey: "critical" },
  { id: "graph",     label: "Clause Graph", icon: NetworkIcon },
  { id: "redlines",  label: "AI Redlines",  icon: Wand2 },
  { id: "contracts", label: "Contracts",    icon: FileText },
  { id: "sows",      label: "SOWs",         icon: FileSignature },
  { id: "reports",   label: "Reports",      icon: BarChart3 },
  { id: "audit",     label: "Audit Trail",  icon: History },
];

const VIEW_TITLES = {
  dashboard: "Executive Dashboard",
  risks:     "Risk Center",
  graph:     "Clause Dependency Graph",
  redlines:  "AI Redlines",
  contracts: "Contracts",
  sows:      "Statements of Work",
  reports:   "Reports",
  audit:     "Audit Trail",
};

const SEV_ORDER = { CRITICAL: 0, BLOCKER: 1, HIGH: 2, MEDIUM: 3, LOW: 4 };
const sevClass   = (s) => ({ CRITICAL: "sev-critical", BLOCKER: "sev-blocker", HIGH: "sev-high", MEDIUM: "sev-medium", LOW: "sev-low" }[s] || "sev-high");
const typeLabel  = (t) => ({ CONTRADICTION: "Contradiction", OVERRIDE: "Override", CIRCULAR_REFERENCE: "Circular Loop", MISSING_DOCUMENT: "Missing Doc" }[t] || t);

// ─── KPI Card ────────────────────────────────────────────────────────────────
const KpiCard = ({ icon: Icon, label, value, sub, color, iconBg, iconColor }) => (
  <div className={`kpi kpi-${color}`}>
    <div className="kpi-label">{label}</div>
    <div className="kpi-value">{value}</div>
    {sub && <div className="kpi-sub">{sub}</div>}
    <div className="kpi-icon" style={{ background: iconBg }}>
      <Icon style={{ width: 18, height: 18, color: iconColor }} />
    </div>
  </div>
);

// ─── Dashboard View ──────────────────────────────────────────────────────────
const DashboardView = ({ nodes, edges, risks, stats, history, onNav }) => {
  const byType = useMemo(() => {
    const acc = { CONTRADICTION: 0, OVERRIDE: 0, CIRCULAR_REFERENCE: 0, MISSING_DOCUMENT: 0 };
    risks.forEach((r) => { if (acc[r.type] != null) acc[r.type]++; });
    return acc;
  }, [risks]);

  const riskBreakdown = [
    { label: "Contradiction",  count: byType.CONTRADICTION,     color: "#DC2626", bg: "#FEF2F2" },
    { label: "Override",       count: byType.OVERRIDE,          color: "#C2410C", bg: "#FFF7ED" },
    { label: "Circular Loop",  count: byType.CIRCULAR_REFERENCE,color: "#6D28D9", bg: "#F5F3FF" },
    { label: "Missing Doc",    count: byType.MISSING_DOCUMENT,  color: "#B45309", bg: "#FFFBEB" },
  ];
  const maxCount = Math.max(1, ...riskBreakdown.map((r) => r.count));

  return (
    <div className="page-wrap">
      {/* Human Review Required Banner */}
      {stats.criticalCount > 0 && (
        <div className="review-banner">
          <div style={{ width: 36, height: 36, background: "#FECACA", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <AlertTriangle style={{ width: 18, height: 18, color: "#DC2626" }} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#991B1B" }}>Human Review Required</div>
            <div style={{ fontSize: 12, color: "#DC2626", marginTop: 2 }}>
              {stats.criticalCount} critical or blocker issue{stats.criticalCount !== 1 ? "s" : ""} detected — legal sign-off required before contract execution.
            </div>
          </div>
          <button className="btn-sm" style={{ background: "#DC2626", color: "white", borderColor: "#DC2626" }} onClick={() => onNav("risks")}>
            Review Issues →
          </button>
        </div>
      )}

      {/* KPI Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 24 }}>
        <KpiCard icon={FileText}      label="Clauses Analyzed"   value={nodes.length}         sub="MSA + SOW corpus"         color="blue"  iconBg="#EEF2FF" iconColor="#6366F1" />
        <KpiCard icon={AlertTriangle} label="Risks Detected"     value={stats.riskCount}      sub="Across both documents"    color="red"   iconBg="#FFF1F2" iconColor="#E11D48" />
        <KpiCard icon={GitBranch}     label="Dependencies Mapped" value={edges.length}        sub="Cross-clause references"  color="teal"  iconBg="#F0FDFA" iconColor="#0D9488" />
        <KpiCard icon={TrendingUp}    label="Critical Findings"  value={stats.criticalCount}  sub="Blocker / critical level"  color="amber" iconBg="#FFFBEB" iconColor="#F59E0B" />
      </div>

      {/* Middle Row: Risk Breakdown + AI Synthesis */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 16, marginBottom: 24 }}>

        {/* Risk Breakdown */}
        <div className="card fade-up">
          <div className="card-header">
            <span className="card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <BarChart3 style={{ width: 16, height: 16, color: "#6366F1" }} /> Risk Distribution by Type
            </span>
            <span style={{ fontSize: 11, color: "#94A3B8", fontWeight: 600 }}>{stats.riskCount} total findings</span>
          </div>
          <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {riskBreakdown.map((r) => (
              <div key={r.label}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: "#374151" }}>{r.label}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: r.count ? r.color : "#94A3B8" }}>{r.count}</span>
                </div>
                <div style={{ height: 8, background: "#F1F5F9", borderRadius: 99 }}>
                  <div style={{ height: "100%", borderRadius: 99, background: r.count ? r.color : "#E2E8F0", width: `${(r.count / maxCount) * 100}%`, transition: "width 0.6s ease" }} />
                </div>
              </div>
            ))}
            <div style={{ marginTop: 4, paddingTop: 14, borderTop: "1px solid #F1F5F9", display: "flex", gap: 16 }}>
              <div>
                <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2 }}>MSA Clauses</div>
                <div style={{ fontSize: 20, fontWeight: 800, color: "#0F172A" }}>{stats.msaCount}</div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2 }}>SOW Clauses</div>
                <div style={{ fontSize: 20, fontWeight: 800, color: "#0F172A" }}>{stats.sowCount}</div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2 }}>Clean Clauses</div>
                <div style={{ fontSize: 20, fontWeight: 800, color: "#16A34A" }}>{nodes.length - stats.riskCount}</div>
              </div>
            </div>
          </div>
        </div>

        {/* AI Synthesis Panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card fade-up" style={{ flex: 1 }}>
            <div className="card-header">
              <span className="card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Sparkles style={{ width: 16, height: 16, color: "#4F46E5" }} /> AI Synthesis
              </span>
            </div>
            <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <p style={{ fontSize: 12.5, color: "#475569", lineHeight: 1.65 }}>
                Analysis surfaced{" "}
                <strong style={{ color: "#DC2626" }}>{stats.criticalCount} critical conflict{stats.criticalCount !== 1 ? "s" : ""}</strong>{" "}
                out of {stats.riskCount} total findings across {nodes.length} clauses.
                {byType.OVERRIDE > 0 && <> <strong style={{ color: "#C2410C" }}>{byType.OVERRIDE} SOW clause{byType.OVERRIDE !== 1 ? "s" : ""}</strong> override the governing MSA — review liability and IP exposure first.</>}
                {byType.CIRCULAR_REFERENCE > 0 && <> <strong style={{ color: "#6D28D9" }}>{byType.CIRCULAR_REFERENCE} circular reference{byType.CIRCULAR_REFERENCE !== 1 ? "s" : ""}</strong> create unenforceable penalty clauses.</>}
              </p>
              <button className="btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={() => onNav("risks")}>
                Open Risk Center <ChevronRight style={{ width: 14, height: 14 }} />
              </button>
              <button className="btn-outline" style={{ width: "100%", justifyContent: "center", fontSize: 12 }} onClick={() => onNav("redlines")}>
                View AI Redlines
              </button>
            </div>
          </div>

          {/* Compliance Score */}
          <div className="card fade-up" style={{ padding: "16px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 4 }}>Compliance Score</div>
                <div style={{ fontSize: 28, fontWeight: 800, color: nodes.length && stats.riskCount / nodes.length > 0.3 ? "#DC2626" : "#16A34A" }}>
                  {nodes.length ? Math.round(((nodes.length - stats.riskCount) / nodes.length) * 100) : 100}%
                </div>
                <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 2 }}>Clean clauses ratio</div>
              </div>
              <div style={{ width: 56, height: 56, borderRadius: "50%", background: nodes.length && stats.riskCount / nodes.length > 0.3 ? "#FEF2F2" : "#F0FDF4", border: `3px solid ${nodes.length && stats.riskCount / nodes.length > 0.3 ? "#FECACA" : "#BBF7D0"}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Shield style={{ width: 22, height: 22, color: nodes.length && stats.riskCount / nodes.length > 0.3 ? "#DC2626" : "#16A34A" }} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="card fade-up">
        <div className="card-header">
          <span className="card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <History style={{ width: 15, height: 15, color: "#6366F1" }} /> Recent Analyses
          </span>
          <button className="btn-sm" onClick={() => onNav("audit")}>View all</button>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Document Pair</th>
              <th>Risks Found</th>
              <th>Analyzed</th>
              <th style={{ textAlign: "right" }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {history.length === 0 ? (
              <tr>
                <td style={{ color: "#475569" }}>Sample MSA &amp; SOW (Demo Data)</td>
                <td><span className="severity-pill sev-high">{stats.riskCount} risks</span></td>
                <td style={{ color: "#94A3B8", fontSize: 12 }}>Live preview</td>
                <td style={{ textAlign: "right" }}>
                  <button className="btn-sm" onClick={() => onNav("graph")}>Open Graph</button>
                </td>
              </tr>
            ) : (
              history.slice(0, 6).map((run) => (
                <tr key={run.id}>
                  <td>
                    <div style={{ fontWeight: 500, color: "#0F172A", fontSize: 13 }}>{run.msa_filename}</div>
                    <div style={{ fontSize: 11, color: "#94A3B8" }}>+ {run.sow_filename}</div>
                  </td>
                  <td><span className="severity-pill sev-high">{run.total_risks} risks</span></td>
                  <td style={{ color: "#94A3B8", fontSize: 12 }}>{new Date(run.timestamp).toLocaleString()}</td>
                  <td style={{ textAlign: "right" }}>
                    <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, fontWeight: 700, background: "#EEF2FF", color: "#4338CA", padding: "2px 7px", borderRadius: 4 }}>#{run.id}</span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ─── Risk Center View ────────────────────────────────────────────────────────
const RiskCenterView = ({ risks, nodes, onInspect, onViewRedline }) => {
  const [levelFilter, setLevelFilter] = useState("ALL");
  const [typeFilter, setTypeFilter]   = useState("ALL");
  const [sortBy, setSortBy]           = useState("severity");

  const nodeFor = (r) => nodes.find((n) => n.id === (r.clause_b_section || r.clause_a_section));

  const findings = useMemo(() => {
    return risks
      .filter((r) => (levelFilter === "ALL" || r.severity === levelFilter) && (typeFilter === "ALL" || r.type === typeFilter))
      .sort((a, b) => sortBy === "type"
        ? String(a.type).localeCompare(String(b.type))
        : (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9));
  }, [risks, levelFilter, typeFilter, sortBy]);

  const critCount = risks.filter((r) => r.severity === "CRITICAL" || r.severity === "BLOCKER").length;

  return (
    <div className="page-wrap">
      {critCount > 0 && (
        <div className="review-banner">
          <AlertCircle style={{ width: 18, height: 18, color: "#DC2626", flexShrink: 0 }} />
          <div style={{ flex: 1, fontSize: 13, color: "#991B1B", fontWeight: 600 }}>
            {critCount} issue{critCount !== 1 ? "s" : ""} require immediate human review before contract signing.
          </div>
        </div>
      )}

      {/* Filter bar */}
      <div className="card" style={{ padding: "14px 20px", marginBottom: 16, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginRight: 4 }}>Filter:</span>
        <select className="filter-select" value={levelFilter} onChange={(e) => setLevelFilter(e.target.value)}>
          <option value="ALL">All Severities</option>
          <option value="CRITICAL">Critical</option>
          <option value="BLOCKER">Blocker</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
        <select className="filter-select" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="ALL">All Types</option>
          <option value="CONTRADICTION">Contradiction</option>
          <option value="OVERRIDE">Override</option>
          <option value="CIRCULAR_REFERENCE">Circular Loop</option>
          <option value="MISSING_DOCUMENT">Missing Doc</option>
        </select>
        <select className="filter-select" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          <option value="severity">Sort: Severity</option>
          <option value="type">Sort: Type</option>
        </select>
        {(levelFilter !== "ALL" || typeFilter !== "ALL") && (
          <button className="btn-sm" onClick={() => { setLevelFilter("ALL"); setTypeFilter("ALL"); }}>Clear filters</button>
        )}
        <span style={{ marginLeft: "auto", fontSize: 12, color: "#94A3B8", fontWeight: 600 }}>
          {findings.length} of {risks.length} findings
        </span>
      </div>

      {/* Findings Table */}
      <div className="card fade-up" style={{ overflow: "hidden" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: 120 }}>Severity</th>
              <th style={{ width: 140 }}>Type</th>
              <th>Clause &amp; Description</th>
              <th style={{ width: 240 }}>AI Recommendation</th>
              <th style={{ width: 130, textAlign: "right" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((r, idx) => {
              const node = nodeFor(r);
              const docType = node?.document_type || (r.clause_b_section || "").split("-")[0];
              return (
                <tr key={`${r.risk_id || "r"}-${idx}`}>
                  <td><span className={`severity-pill ${sevClass(r.severity)}`}>{r.severity}</span></td>
                  <td>
                    <span className={`type-tag type-${r.type}`}>{typeLabel(r.type)}</span>
                  </td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>
                      <span className={`clause-chip ${docType === "MSA" ? "chip-msa" : "chip-sow"}`}>{r.clause_b_section || r.clause_a_section}</span>
                      {node && <span style={{ fontSize: 12, fontWeight: 600, color: "#0F172A" }}>{node.title}</span>}
                    </div>
                    <p style={{ fontSize: 12, color: "#475569", lineHeight: 1.55, margin: 0 }}>{r.description}</p>
                  </td>
                  <td>
                    {r.which_wins ? (
                      <div className="ai-box">
                        <strong>AI:</strong> {r.which_wins}
                      </div>
                    ) : (
                      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#C2410C", fontWeight: 600 }}>
                        <AlertTriangle style={{ width: 13, height: 13 }} /> Human review required
                      </div>
                    )}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 6 }}>
                      {r.suggested_text && (
                        <button className="btn-sm" onClick={() => onViewRedline(r.clause_b_section || r.clause_a_section)}>Redline</button>
                      )}
                      <button className="btn-sm" onClick={() => onInspect(r.clause_b_section || r.clause_a_section)}>Inspect</button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {findings.length === 0 && (
              <tr>
                <td colSpan="5" style={{ textAlign: "center", padding: "40px 0", color: "#94A3B8", fontSize: 13 }}>
                  No findings match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ─── Audit Trail View ────────────────────────────────────────────────────────
const AuditView = ({ history, loadAnalysis, loading, onRefresh }) => (
  <div className="page-wrap">
    <div className="card fade-up" style={{ overflow: "hidden" }}>
      <div className="card-header">
        <span className="card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <History style={{ width: 15, height: 15, color: "#6366F1" }} /> Audit Trail
        </span>
        <button className="btn-outline" style={{ fontSize: 12, padding: "6px 12px" }} onClick={onRefresh}>
          <RotateCcw style={{ width: 13, height: 13 }} /> Refresh
        </button>
      </div>
      {history.length === 0 ? (
        <div style={{ padding: "48px 0", textAlign: "center", color: "#94A3B8", fontSize: 13 }}>
          No past audits yet. Run an analysis to build the audit trail.
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>MSA Document</th>
              <th>SOW Document</th>
              <th>Risks</th>
              <th>Date &amp; Time</th>
              <th style={{ textAlign: "right" }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {history.map((run) => (
              <tr key={run.id}>
                <td>
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, fontWeight: 700, background: "#EEF2FF", color: "#4338CA", padding: "3px 8px", borderRadius: 4 }}>#{run.id}</span>
                </td>
                <td style={{ fontWeight: 500, color: "#0F172A", fontSize: 13 }}>{run.msa_filename}</td>
                <td style={{ color: "#475569", fontSize: 13 }}>{run.sow_filename}</td>
                <td><span className={`severity-pill ${run.total_risks > 0 ? "sev-high" : "sev-low"}`}>{run.total_risks}</span></td>
                <td style={{ fontSize: 12, color: "#94A3B8" }}>{new Date(run.timestamp).toLocaleString()}</td>
                <td style={{ textAlign: "right" }}>
                  <button className="btn-sm" disabled={loading} onClick={() => loadAnalysis(run.id)}>
                    Load Analysis
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  </div>
);

// ─── Skeleton ────────────────────────────────────────────────────────────────
const SkeletonView = () => (
  <div className="page-wrap">
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 24 }}>
      {[0,1,2,3].map((i) => (
        <div key={i} className="kpi">
          <div className="skeleton" style={{ height: 12, width: "60%", marginBottom: 12 }} />
          <div className="skeleton" style={{ height: 36, width: "40%" }} />
        </div>
      ))}
    </div>
    <div className="card" style={{ padding: 24 }}>
      {[0,1,2,3,4].map((i) => <div key={i} className="skeleton" style={{ height: 44, marginBottom: 12 }} />)}
    </div>
  </div>
);

// ─── Upload Modal ────────────────────────────────────────────────────────────
const UploadModal = ({ onClose, onUpload, msaFile, sowFile, setMsaFile, setSowFile, loading, error }) => {
  const panelRef = useRef(null);

  useEffect(() => {
    const panel = panelRef.current;
    const focusables = () =>
      Array.from(panel?.querySelectorAll("button,input,[tabindex]:not([tabindex='-1'])") || [])
        .filter((el) => !el.disabled && el.offsetParent !== null);
    focusables()[0]?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
      if (e.key !== "Tab") return;
      const items = focusables();
      if (!items.length) return;
      if (e.shiftKey && document.activeElement === items[0]) { e.preventDefault(); items[items.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === items[items.length - 1]) { e.preventDefault(); items[0].focus(); }
    };
    panel?.addEventListener("keydown", onKey);
    return () => panel?.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div ref={panelRef} className="modal-box" role="dialog" aria-modal="true" aria-labelledby="upload-title" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
            <div style={{ width: 40, height: 40, background: "#EEF2FF", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <Wand2 style={{ width: 18, height: 18, color: "#4F46E5" }} />
            </div>
            <div>
              <h2 id="upload-title" style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "#0F172A" }}>Run AI Contract Audit</h2>
              <p style={{ margin: "4px 0 0", fontSize: 12, color: "#64748B" }}>Upload an MSA + SOW pair for full risk analysis</p>
            </div>
          </div>
          <button className="btn-icon" onClick={onClose} aria-label="Close">
            <X style={{ width: 16, height: 16 }} />
          </button>
        </div>

        {/* Body */}
        <div className="modal-body">
          <form onSubmit={onUpload} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label className="input-label">MSA Document (PDF / DOCX)</label>
              <input type="file" accept=".pdf,.docx,.txt" className="file-input" onChange={(e) => setMsaFile(e.target.files[0])} />
              {msaFile && (
                <div style={{ marginTop: 6, fontSize: 11, color: "#16A34A", display: "flex", alignItems: "center", gap: 5 }}>
                  <CheckCircle2 style={{ width: 12, height: 12 }} /> {msaFile.name}
                </div>
              )}
            </div>

            <div>
              <label className="input-label">SOW Document (PDF / DOCX)</label>
              <input type="file" accept=".pdf,.docx,.txt" className="file-input" onChange={(e) => setSowFile(e.target.files[0])} />
              {sowFile && (
                <div style={{ marginTop: 6, fontSize: 11, color: "#16A34A", display: "flex", alignItems: "center", gap: 5 }}>
                  <CheckCircle2 style={{ width: 12, height: 12 }} /> {sowFile.name}
                </div>
              )}
            </div>

            {error && (
              <div style={{ background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 8, padding: "10px 14px", fontSize: 12, color: "#DC2626" }}>
                {error}
              </div>
            )}

            <div style={{ display: "flex", gap: 10, paddingTop: 4 }}>
              <button type="button" className="btn-outline" style={{ flex: 1 }} onClick={onClose}>Cancel</button>
              <button type="submit" className="btn-primary" style={{ flex: 2 }} disabled={loading || !msaFile || !sowFile}>
                {loading
                  ? <><div style={{ width: 14, height: 14, border: "2px solid rgba(255,255,255,0.4)", borderTopColor: "white", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} /> Analyzing…</>
                  : <><Play style={{ width: 14, height: 14 }} /> Run AI Audit</>
                }
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

// ─── Main App ────────────────────────────────────────────────────────────────
function App() {
  const [view, setView]               = useState("dashboard");
  const [modalOpen, setModalOpen]     = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);


  const [searchQuery, setSearchQuery]       = useState("");
  const [searchResults, setSearchResults]   = useState([]);
  const [searchOpen, setSearchOpen]         = useState(false);
  const [notifOpen, setNotifOpen]           = useState(false);
  const [redlineTarget, setRedlineTarget]   = useState(null);
  const [serverModel, setServerModel]       = useState(null);
  const [searchActiveIdx, setSearchActiveIdx] = useState(-1);
  const searchInputRef = useRef(null);

  const [nodes, setNodes]                       = useState(MOCK_NODES);
  const [edges, setEdges]                       = useState(MOCK_EDGES);
  const [circularReferences, setCircularReferences] = useState(MOCK_CYCLES);
  const [risks, setRisks]                       = useState(MOCK_RISKS);
  const [isDemoMode, setIsDemoMode]             = useState(true);
  const [activeAnalysisName, setActiveAnalysisName] = useState("Sample MSA + SOW");

  const [history, setHistory]       = useState([]);
  const [loading, setLoading]       = useState(false);
  const [loadingStep, setLoadingStep]   = useState(0);
  const [loadingStatus, setLoadingStatus] = useState("");
  const [msaFile, setMsaFile]       = useState(null);
  const [sowFile, setSowFile]       = useState(null);
  const [error, setError]           = useState(null);
  const [lastResults, setLastResults] = useState(null);
  const [elapsed, setElapsed]       = useState(0);
  const loadingIntervalRef = useRef(null);
  const elapsedIntervalRef = useRef(null);
  const abortRef = useRef(null);
  const UPLOAD_TIMEOUT_MS = 5 * 60 * 1000;

  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [filters, setFilters] = useState({ showMsa: true, showSow: true, showRisksOnly: false });

  // Graph panel resize state
  const [leftPanelW, setLeftPanelW]   = useState(260);
  const [rightPanelW, setRightPanelW] = useState(280);
  const [graphFullscreen, setGraphFullscreen] = useState(false);
  const graphContainerRef = useRef(null);
  const clauseGraphRef = useRef(null);
  const dragging = useRef(null); // "left" | "right" | null

  useEffect(() => {
    const onMove = (e) => {
      if (!dragging.current || !graphContainerRef.current) return;
      const rect = graphContainerRef.current.getBoundingClientRect();
      if (dragging.current === "left") {
        setLeftPanelW(Math.max(180, Math.min(420, e.clientX - rect.left)));
      } else {
        setRightPanelW(Math.max(180, Math.min(420, rect.right - e.clientX)));
      }
    };
    const onUp = () => { dragging.current = null; document.body.style.cursor = ""; document.body.style.userSelect = ""; };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => { document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onUp); };
  }, []);

  const LOADING_STEPS = [
    "Uploading documents to analysis engine…",
    "AI extracting clauses and obligations…",
    "Building dependency graph…",
    "Detecting contradictions & overrides…",
    "Generating AI redline suggestions…",
    "Finalising audit trail…",
  ];

  const startLoadingCycle = () => {
    setLoadingStep(0); setLoadingStatus(LOADING_STEPS[0]); setElapsed(0);
    let step = 0;
    loadingIntervalRef.current = setInterval(() => {
      step = Math.min(step + 1, LOADING_STEPS.length - 1);
      setLoadingStep(step); setLoadingStatus(LOADING_STEPS[step]);
    }, 4000);
    elapsedIntervalRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
  };
  const stopLoadingCycle = () => {
    if (loadingIntervalRef.current) { clearInterval(loadingIntervalRef.current); loadingIntervalRef.current = null; }
    if (elapsedIntervalRef.current) { clearInterval(elapsedIntervalRef.current); elapsedIntervalRef.current = null; }
  };

  const handleExport = () => {
    if (!lastResults) return;
    const blob = new Blob([JSON.stringify(lastResults, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `techm-legal-audit-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    (async () => {
      try {
        const h = await fetch(`${BACKEND_URL}/health`);
        if (h.ok) { const info = await h.json(); if (info.model) setServerModel(info.model); }
      } catch { /**/ }
      const runs = await fetchHistory();
      if (runs?.length > 0) {
        try {
          const res = await fetch(`${BACKEND_URL}/analysis/${runs[0].id}`);
          if (res.ok) {
            const data = await res.json();
            applyAnalysis(data, `${data.msa_filename} + ${data.sow_filename}`);
          }
        } catch { /**/ }
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/history`);
      if (res.ok) { const data = await res.json(); setHistory(data); return data; }
    } catch (err) { console.error("fetchHistory:", err); }
    return [];
  };

  const applyAnalysis = (data, name) => {
    const nodesList  = data.graph?.nodes || [];
    const edgesList  = data.graph?.edges || [];
    const cyclesList = data.graph?.circular_references || [];
    const risksMap   = buildRisksMap(extractRiskList(data));
    setNodes(mapNodesWithRisk(nodesList, risksMap));
    setEdges(edgesList);
    setCircularReferences(cyclesList);
    setRisks(risksMap);
    setIsDemoMode(false);
    setActiveAnalysisName(name);
    setSelectedNodeId(null);
    setLastResults(data);
  };

  const loadAnalysis = async (id, targetSection = null, targetView = "graph") => {
    setLoading(true); setError(null); setLoadingStatus("Retrieving audit record…");
    try {
      const res = await fetch(`${BACKEND_URL}/analysis/${id}`);
      if (!res.ok) throw new Error(`Failed to load (${res.status})`);
      const data = await res.json();
      applyAnalysis(data, `${data.msa_filename} + ${data.sow_filename}`);
      if (targetSection) setSelectedNodeId(targetSection);
      setView(targetView);
    } catch (err) { setError(`Load error: ${err.message}`); }
    finally { setLoading(false); }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!msaFile || !sowFile) { setError("Select both MSA and SOW files first."); return; }
    setLoading(true); setError(null); startLoadingCycle(); setModalOpen(false); setView("graph");
    const controller = new AbortController();
    abortRef.current = controller;
    const tid = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);
    try {
      const form = new FormData();
      form.append("msa_file", msaFile);
      form.append("sow_file", sowFile);
      const res = await fetch(`${BACKEND_URL}/upload`, { method: "POST", body: form, signal: controller.signal });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Server ${res.status}`); }
      applyAnalysis(await res.json(), `${msaFile.name} + ${sowFile.name}`);
      fetchHistory();
    } catch (err) {
      setError(err.name === "AbortError"
        ? "Analysis timed out (>5 min). API may be rate-limited. Please retry."
        : `Analysis failed: ${err.message}`);
      setView("graph");
    } finally { clearTimeout(tid); abortRef.current = null; stopLoadingCycle(); setLoading(false); }
  };

  const handleNodeClick = (nodeId) => setSelectedNodeId(nodeId);
  const inspectFromRisk = (nodeId) => { setSelectedNodeId(nodeId); setNotifOpen(false); setView("graph"); };
  const viewRedline     = (section) => { setRedlineTarget(section); setView("redlines"); };

  useEffect(() => {
    const q = searchQuery.trim();
    if (q.length < 2) { setSearchResults([]); return; }
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/search?q=${encodeURIComponent(q)}`);
        if (res.ok) setSearchResults(await res.json());
      } catch { /**/ }
    }, 250);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const openSearchResult = (r) => {
    setSearchOpen(false); setSearchQuery("");
    loadAnalysis(r.analysis_id, r.section, r.kind === "risk" ? "redlines" : "graph");
  };

  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 6000);
    return () => clearTimeout(t);
  }, [error]);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); searchInputRef.current?.focus(); setSearchOpen(true); }
      else if (e.key === "Escape") { setNotifOpen(false); setGraphFullscreen(false); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => { setSearchActiveIdx(-1); }, [searchResults]);

  const onSearchKeyDown = (e) => {
    if (!searchOpen || searchResults.length === 0) {
      if (e.key === "Escape") { setSearchOpen(false); e.currentTarget.blur(); }
      return;
    }
    if (e.key === "ArrowDown") { e.preventDefault(); setSearchActiveIdx((i) => Math.min(i + 1, searchResults.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSearchActiveIdx((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { const r = searchResults[searchActiveIdx] || searchResults[0]; if (r) openSearchResult(r); }
    else if (e.key === "Escape") { setSearchOpen(false); e.currentTarget.blur(); }
  };

  useEffect(() => {
    if (["audit","contracts","sows","reports","dashboard"].includes(view)) fetchHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  const selectedClause = useMemo(() => nodes.find((n) => n.id === selectedNodeId), [nodes, selectedNodeId]);
  const selectedRisk   = useMemo(() => (selectedNodeId ? risks[selectedNodeId] || null : null), [risks, selectedNodeId]);
  const allRisks       = useMemo(() => dedupeRisks(risks), [risks]);
  const graphEdges     = useMemo(() => [...edges, ...buildRiskEdges(allRisks)], [edges, allRisks]);
  const stats          = useMemo(() => computeStats(nodes, allRisks), [nodes, allRisks]);
  const badgeValue     = { critical: stats.criticalCount };
  const criticalFindings = useMemo(() => allRisks.filter((r) => r.severity === "CRITICAL" || r.severity === "BLOCKER").slice(0, 8), [allRisks]);
  const unmappedCount  = useMemo(() => countUnmapped(nodes, allRisks), [nodes, allRisks]);

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#F1F5F9" }}>

      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <aside className="app-sidebar">
        {/* Brand */}
        <div className="sidebar-brand">
          <div className="brand-icon">
            <Scale style={{ width: 18, height: 18, color: "white" }} />
          </div>
          <div>
            <div className="brand-title">TechMcode</div>
            <div className="brand-sub">Legal AI Platform</div>
          </div>
        </div>

        {/* Navigation */}
        <div className="sidebar-section-label">Main Menu</div>
        <nav style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2, overflowY: "auto" }}>
          {NAV_ITEMS.map((item) => {
            const badge = item.badgeKey ? badgeValue[item.badgeKey] : 0;
            const active = view === item.id;
            return (
              <button
                key={item.id}
                className={`nav-btn${active ? " active" : ""}`}
                onClick={() => setView(item.id)}
              >
                <item.icon className="nav-icon" />
                <span style={{ flex: 1, textAlign: "left" }}>{item.label}</span>
                {badge > 0 && <span className="nav-badge">{badge}</span>}
              </button>
            );
          })}
        </nav>

        {/* Bottom CTA */}
        <div className="sidebar-cta">
          <button
            className="btn-primary"
            style={{ width: "100%", justifyContent: "center", borderRadius: 9, padding: "10px 0" }}
            onClick={() => { setError(null); setModalOpen(true); }}
          >
            <Plus style={{ width: 15, height: 15 }} /> Run AI Audit
          </button>
          {serverModel && (
            <div style={{ marginTop: 10, fontSize: 10, color: "#475569", textAlign: "center", letterSpacing: "0.03em" }}>
              <Zap style={{ width: 10, height: 10, display: "inline", marginRight: 3 }} />
              {serverModel}
            </div>
          )}
        </div>
      </aside>

      {/* ── Main ──────────────────────────────────────────────────────────── */}
      <div className="app-main">
        {/* Top Bar */}
        <header className="app-topbar">
          {/* Title */}
          <span className="topbar-title">{VIEW_TITLES[view]}</span>

          {/* Active analysis name — truncates gracefully */}
          {activeAnalysisName && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0, maxWidth: 260, overflow: "hidden" }}>
              <span style={{ color: "#CBD5E1", flexShrink: 0 }}>|</span>
              <span style={{ fontSize: 11.5, color: "#64748B", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={activeAnalysisName}>
                {activeAnalysisName}
              </span>
            </div>
          )}

          {/* Search */}
          <div style={{ position: "relative", marginLeft: "auto" }}>
            <div className="search-box">
              <Search style={{ width: 14, height: 14, color: "#94A3B8", flexShrink: 0 }} />
              <input
                ref={searchInputRef}
                placeholder="Search clauses, risks… (⌘K)"
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setSearchOpen(true); }}
                onFocus={() => setSearchOpen(true)}
                onBlur={() => setTimeout(() => setSearchOpen(false), 150)}
                onKeyDown={onSearchKeyDown}
              />
            </div>
            {searchOpen && searchQuery.trim().length >= 2 && (
              <div className="dropdown-search-panel">
                {searchResults.length === 0 ? (
                  <div style={{ padding: "16px", fontSize: 12, color: "#94A3B8", textAlign: "center" }}>No results for "{searchQuery}"</div>
                ) : searchResults.map((r, i) => (
                  <button key={i} className="dd-item" onMouseDown={() => openSearchResult(r)}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                      <span className={`clause-chip ${r.section?.startsWith?.("MSA") ? "chip-msa" : "chip-sow"}`}>{r.section || r.kind}</span>
                      {r.severity && <span className={`severity-pill ${sevClass(r.severity)}`} style={{ fontSize: 9, padding: "1px 6px" }}>{r.severity}</span>}
                      <span style={{ fontSize: 12, fontWeight: 600, color: "#0F172A" }}>{r.title}</span>
                    </div>
                    <div style={{ fontSize: 11, color: "#64748B" }}>{r.text}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Status badge */}
          <div className={`status-badge ${isDemoMode ? "demo" : "live"}`}>
            <div className={`dot ${isDemoMode ? "dot-demo" : "dot-live"}`} />
            {isDemoMode ? "Demo Mode" : "Live Engine"}
          </div>

          {/* Notifications */}
          <div style={{ position: "relative" }}>
            <button
              className="btn-icon"
              onClick={() => setNotifOpen((v) => !v)}
              aria-label="Notifications"
              style={{ position: "relative" }}
            >
              <Bell style={{ width: 18, height: 18 }} />
              {criticalFindings.length > 0 && (
                <span style={{ position: "absolute", top: 4, right: 4, width: 8, height: 8, background: "#DC2626", borderRadius: "50%", border: "2px solid white" }} />
              )}
            </button>
            {notifOpen && (
              <div className="dropdown-panel" onMouseLeave={() => setNotifOpen(false)}>
                <div style={{ padding: "12px 16px 10px", borderBottom: "1px solid #F1F5F9", display: "flex", alignItems: "center", gap: 8 }}>
                  <ShieldAlert style={{ width: 14, height: 14, color: "#DC2626" }} />
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#0F172A" }}>Critical Findings</span>
                  <span style={{ marginLeft: "auto", fontSize: 11, color: "#94A3B8" }}>{criticalFindings.length}</span>
                </div>
                {criticalFindings.length === 0 ? (
                  <div style={{ padding: 16, fontSize: 12, color: "#94A3B8", textAlign: "center" }}>No critical findings.</div>
                ) : criticalFindings.map((r, i) => (
                  <button key={i} className="dd-item" onMouseDown={() => inspectFromRisk(r.clause_b_section || r.clause_a_section)}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                      <span className={`severity-pill ${sevClass(r.severity)}`} style={{ fontSize: 9, padding: "1px 6px" }}>{r.severity}</span>
                      <span className="clause-chip chip-msa">{r.clause_b_section || r.clause_a_section}</span>
                    </div>
                    <div style={{ fontSize: 11, color: "#475569" }}>{r.description?.slice(0, 80)}…</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Settings */}
          <button className="btn-icon" onClick={() => setSettingsOpen(true)} aria-label="Settings">
            <Settings style={{ width: 16, height: 16 }} />
          </button>

          {/* Export */}
          {lastResults && (
            <button className="btn-outline" style={{ fontSize: 12, padding: "6px 12px" }} onClick={handleExport}>
              <Download style={{ width: 13, height: 13 }} /> Export
            </button>
          )}
        </header>

        {/* Content */}
        <div className="content-area">
          {loading && view !== "graph" && <SkeletonView />}

          {!loading && view === "dashboard" && (
            <DashboardView nodes={nodes} edges={edges} risks={allRisks} stats={stats} history={history} onNav={setView} />
          )}
          {!loading && view === "risks" && (
            <RiskCenterView risks={allRisks} nodes={nodes} onInspect={inspectFromRisk} onViewRedline={viewRedline} />
          )}
          {!loading && view === "audit" && (
            <AuditView history={history} loadAnalysis={loadAnalysis} loading={loading} onRefresh={fetchHistory} />
          )}
          {!loading && view === "contracts" && (
            <DocumentsView history={history} field="msa_filename" kind="MSA" onOpen={loadAnalysis} onNew={() => { setError(null); setModalOpen(true); }} />
          )}
          {!loading && view === "sows" && (
            <DocumentsView history={history} field="sow_filename" kind="SOW" onOpen={loadAnalysis} onNew={() => { setError(null); setModalOpen(true); }} />
          )}
          {!loading && view === "redlines" && (
            <div style={{ background: "#060911", minHeight: "100%", overflow: "auto" }}>
              <ReviewWorkspace nodes={nodes} risks={risks} allRisks={allRisks} initialSection={redlineTarget} backendUrl={BACKEND_URL} />
            </div>
          )}
          {!loading && view === "reports" && (
            <ReportsView history={history} allRisks={allRisks} activeAnalysisName={activeAnalysisName} onExportJson={lastResults ? handleExport : null} />
          )}

          {/* Graph View */}
          {view === "graph" && (
            <div
              ref={graphContainerRef}
              style={{
                display: "flex",
                height: "100%",
                position: graphFullscreen ? "fixed" : "relative",
                inset: graphFullscreen ? 0 : "auto",
                zIndex: graphFullscreen ? 999 : "auto",
                background: "#F8FAFC",
              }}
            >
              {/* Left panel */}
              {!graphFullscreen && (
                <>
                  <div style={{ width: leftPanelW, minWidth: leftPanelW, background: "#0F172A", display: "flex", flexDirection: "column", overflowY: "auto", flexShrink: 0 }}>
                    <div style={{ padding: "16px 14px", borderBottom: "1px solid #1E293B" }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 10 }}>Analysis Overview</div>
                      <p style={{ fontSize: 12, color: "#64748B", lineHeight: 1.6, margin: "0 0 12px" }}>
                        Interactive graph of <strong style={{ color: "#818CF8" }}>MSA</strong> and <strong style={{ color: "#34D399" }}>SOW</strong> clause dependencies. Click any node to inspect.
                      </p>
                      <button className="btn-outline" style={{ width: "100%", justifyContent: "center", fontSize: 12, background: "#1E293B", borderColor: "#334155", color: "#94A3B8" }} onClick={() => { setError(null); setModalOpen(true); }}>
                        <Upload style={{ width: 13, height: 13 }} /> Analyze New Docs
                      </button>
                    </div>
                    <div style={{ padding: "12px 14px" }}>
                      <GraphControls filters={filters} onChange={setFilters} />
                    </div>
                    <div style={{ padding: "0 14px 12px" }}>
                      <GraphLegend />
                    </div>
                    <div style={{ padding: "0 14px 12px" }}>
                      <CycleWarning circularReferences={circularReferences} onSelectNode={setSelectedNodeId} />
                    </div>
                  </div>

                  {/* Left drag handle */}
                  <div
                    onMouseDown={(e) => { e.preventDefault(); dragging.current = "left"; document.body.style.cursor = "col-resize"; document.body.style.userSelect = "none"; }}
                    style={{ width: 4, cursor: "col-resize", background: "#1E293B", flexShrink: 0, transition: "background 0.15s" }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#3B82F6"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "#1E293B"; }}
                  />
                </>
              )}

              {/* Graph canvas */}
              <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "#F8FAFC", minWidth: 0 }}>
                <div style={{ padding: "10px 16px", background: "white", borderBottom: "1px solid #E2E8F0", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "#0F172A", display: "flex", alignItems: "center", gap: 8 }}>
                      <CircleDot style={{ width: 15, height: 15, color: "#4F46E5" }} /> Clause Dependency Graph
                    </div>
                    <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 1 }}>Physics-driven interactive clause map</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {unmappedCount > 0 && (
                      <button className="severity-pill sev-medium" style={{ cursor: "pointer" }} onClick={() => setView("risks")}>
                        {unmappedCount} not on graph
                      </button>
                    )}
                    {selectedNodeId && (
                      <button className="btn-outline" style={{ fontSize: 11, padding: "5px 10px" }} onClick={() => setSelectedNodeId(null)}>Clear</button>
                    )}
                    <button
                      className="btn-outline"
                      style={{ fontSize: 11, padding: "5px 10px", display: "flex", alignItems: "center", gap: 5 }}
                      title="Fit all nodes in view"
                      onClick={() => clauseGraphRef.current?.fit()}
                    >
                      <Crosshair style={{ width: 13, height: 13 }} /> Fit
                    </button>
                    <button
                      className="btn-icon"
                      title={graphFullscreen ? "Exit fullscreen" : "Fullscreen graph"}
                      onClick={() => setGraphFullscreen((v) => !v)}
                    >
                      {graphFullscreen
                        ? <Minimize2 style={{ width: 16, height: 16 }} />
                        : <Expand style={{ width: 16, height: 16 }} />
                      }
                    </button>
                  </div>
                </div>

                {loading ? (
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 40, gap: 16, textAlign: "center" }}>
                    <div style={{ position: "relative" }}>
                      <div style={{ width: 56, height: 56, border: "3px solid #E2E8F0", borderTopColor: "#2563EB", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                      <Scale style={{ width: 20, height: 20, color: "#6366F1", position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)" }} />
                    </div>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: "#0F172A", marginBottom: 4 }}>{loadingStatus}</div>
                      <div style={{ fontSize: 12, color: "#94A3B8", fontFamily: "JetBrains Mono, monospace" }}>
                        {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")} elapsed
                      </div>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%", maxWidth: 280 }}>
                      {LOADING_STEPS.map((step, i) => (
                        <div key={i} className={`loading-step${i < loadingStep ? " done" : i === loadingStep ? " active" : ""}`}>
                          {i < loadingStep
                            ? <CheckCircle2 style={{ width: 14, height: 14, flexShrink: 0 }} />
                            : i === loadingStep
                            ? <div style={{ width: 14, height: 14, border: "2px solid #2563EB", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite", flexShrink: 0 }} />
                            : <div style={{ width: 14, height: 14, border: "2px solid #E2E8F0", borderRadius: "50%", flexShrink: 0 }} />
                          }
                          {step}
                        </div>
                      ))}
                    </div>
                    {elapsed > 20 && (
                      <p style={{ fontSize: 11, color: "#94A3B8", maxWidth: 280 }}>
                        Live AI analysis takes 1–2 minutes. Free-tier Gemini keys are rate-limited.
                      </p>
                    )}
                    <button className="btn-outline" style={{ fontSize: 12 }} onClick={() => abortRef.current?.abort()}>Cancel Analysis</button>
                  </div>
                ) : (
                  <div style={{ flex: 1, position: "relative" }}>
                    <Suspense fallback={
                      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#94A3B8", fontSize: 13 }}>
                        Loading graph engine…
                      </div>
                    }>
                      <ClauseGraph ref={clauseGraphRef} nodes={nodes} edges={graphEdges} circularReferences={circularReferences} selectedNodeId={selectedNodeId} onNodeClick={handleNodeClick} filters={filters} />
                    </Suspense>
                  </div>
                )}
              </div>

              {/* Right drag handle + inspector */}
              {!graphFullscreen && (
                <>
                  {/* Right drag handle */}
                  <div
                    onMouseDown={(e) => { e.preventDefault(); dragging.current = "right"; document.body.style.cursor = "col-resize"; document.body.style.userSelect = "none"; }}
                    style={{ width: 4, cursor: "col-resize", background: "#E2E8F0", flexShrink: 0, transition: "background 0.15s" }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#3B82F6"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "#E2E8F0"; }}
                  />

                  {/* Right inspector */}
                  <div style={{ width: rightPanelW, minWidth: rightPanelW, background: "#0F172A", borderLeft: "1px solid #1E293B", overflow: "hidden", flexShrink: 0 }}>
                    {selectedClause ? (
                      <GraphSidePanel clause={selectedClause} risk={selectedRisk} onClose={() => setSelectedNodeId(null)} />
                    ) : (
                      <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 32, textAlign: "center" }}>
                        <div style={{ width: 48, height: 48, background: "rgba(99,102,241,0.12)", borderRadius: 14, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 14, border: "1px solid rgba(99,102,241,0.2)" }}>
                          <Maximize2 style={{ width: 20, height: 20, color: "#818CF8" }} />
                        </div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "#E2E8F0", marginBottom: 6 }}>Node Inspector</div>
                        <p style={{ fontSize: 11, lineHeight: 1.7, color: "#475569", maxWidth: 190 }}>
                          Click any clause node in the graph to inspect its text, relationships, and AI-generated redline suggestions.
                        </p>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      {modalOpen && (
        <UploadModal
          onClose={() => setModalOpen(false)} onUpload={handleUpload}
          msaFile={msaFile} sowFile={sowFile} setMsaFile={setMsaFile} setSowFile={setSowFile}
          loading={loading} error={error}
        />
      )}
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} currentModel={serverModel} />}

      {/* Toast */}
      {error && !modalOpen && (
        <div className="toast" role="alert">
          <AlertTriangle style={{ width: 16, height: 16, color: "#DC2626", flexShrink: 0, marginTop: 1 }} />
          <span style={{ flex: 1, fontSize: 12, color: "#991B1B" }}>{error}</span>
          <button className="btn-icon" style={{ width: 28, height: 28 }} onClick={() => setError(null)} aria-label="Dismiss">
            <X style={{ width: 14, height: 14 }} />
          </button>
        </div>
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @media (min-width: 1024px) { .lg-only { display: flex !important; } }
        @media (max-width: 1023px) { .lg-only { display: none !important; } .app-sidebar { position: fixed; } }
      `}</style>
    </div>
  );
}

export default App;
