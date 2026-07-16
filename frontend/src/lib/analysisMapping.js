/**
 * Pure helpers for turning a backend analysis payload into the shapes the UI
 * renders. Extracted from App.jsx so the risk-mapping and dedup rules can be
 * unit-tested without mounting the component.
 */

/** /upload returns `results`; /analysis/{id} returns `risks` — accept either.
 *  Backend also returns missing_docs as a separate array — merge them in. */
export function extractRiskList(data) {
  const results = data?.results || data?.risks || [];
  const missingDocs = (data?.missing_docs || []).map((m) => ({
    risk_id: m.risk_id || `MISSING-${m.referenced_document}`,
    type: "MISSING_DOCUMENT",
    severity: m.severity || "BLOCKER",
    clause_a_section: m.clause_section || `missing:${m.referenced_document}`,
    clause_b_section: null,
    description: m.description || `Referenced document not uploaded: "${m.referenced_document}"`,
    referenced_document: m.referenced_document,
    which_wins: null,
    suggested_text: null,
  }));
  return [...results, ...missingDocs];
}

/**
 * Build a map from clause section → risk. Keyed by BOTH clause_b_section and
 * clause_a_section (skipping nulls) so a highlight/lookup works regardless of
 * which side the finding recorded. First writer wins for a given section.
 */
export function buildRisksMap(riskList) {
  const risksMap = {};
  (riskList || []).forEach((risk) => {
    [risk.clause_b_section, risk.clause_a_section].forEach((key) => {
      if (key && !risksMap[key]) risksMap[key] = risk;
    });
  });
  return risksMap;
}

/**
 * Apply has_risk to each node: a node is risky if the backend flagged it OR a
 * detected risk maps to its section. Must be a boolean OR, not `??` — the graph
 * is built before risk detection, so every node arrives with has_risk === false
 * (not null), and `??` would keep that false and never derive from the risk map.
 */
export function mapNodesWithRisk(nodesList, risksMap) {
  return (nodesList || []).map((n) => ({
    ...n,
    has_risk: Boolean(n.has_risk) || !!risksMap[n.id],
  }));
}

/**
 * Flatten the section→risk map into a de-duplicated list. Because a single risk
 * is keyed under two sections, dedup must be by OBJECT REFERENCE — risk_id is
 * not unique/reliable in real data.
 */
export function dedupeRisks(risksMap) {
  const seen = new Set();
  const out = [];
  Object.values(risksMap || {}).forEach((r) => {
    if (!seen.has(r)) { seen.add(r); out.push(r); }
  });
  return out;
}

/**
 * Build graph edges from the detected risks. The backend's dependency graph
 * (Component 3) only carries structural clause references — it never includes
 * the conflicts that Component 4 finds. So the actual MSA↔SOW conflict links are
 * invisible on the graph unless we synthesise them here from each risk that ties
 * two clauses together. The edge carries `conflict_type` so it can be drawn and
 * labelled by the kind of conflict (contradiction / override / circular).
 */
export function buildRiskEdges(allRisks) {
  const out = [];
  const seen = new Set();
  (allRisks || []).forEach((r) => {
    const a = r.clause_a_section;
    const b = r.clause_b_section;
    if (!a || !b || a === b) return; // need two distinct clause nodes to draw a link
    const type = r.type || "CONTRADICTION";
    const key = `${a}|${b}|${type}`;
    if (seen.has(key)) return;
    seen.add(key);
    let edge_type = "contradiction";
    if (type === "OVERRIDE") edge_type = "override";
    else if (type === "CIRCULAR_REFERENCE") edge_type = "circular";
    out.push({ from: a, to: b, edge_type, conflict_type: type, is_risk_edge: true });
  });
  return out;
}

const isCritical = (r) => r.severity === "CRITICAL" || r.severity === "BLOCKER";

/** Dashboard summary counts. */
export function computeStats(nodes, allRisks) {
  return {
    msaCount: (nodes || []).filter((n) => n.document_type === "MSA").length,
    sowCount: (nodes || []).filter((n) => n.document_type === "SOW").length,
    riskCount: (allRisks || []).length,
    criticalCount: (allRisks || []).filter(isCritical).length,
  };
}

/**
 * Findings whose clause has no corresponding graph node (e.g. missing-doc risks
 * or a null section) — they show in Risk Center but never light up the graph.
 */
export function countUnmapped(nodes, allRisks) {
  const ids = new Set((nodes || []).map((n) => n.id));
  return (allRisks || []).filter((r) => {
    const s = r.clause_b_section || r.clause_a_section;
    return !s || !ids.has(s);
  }).length;
}
