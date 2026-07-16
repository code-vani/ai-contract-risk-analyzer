import { describe, it, expect } from "vitest";
import {
  extractRiskList,
  buildRisksMap,
  mapNodesWithRisk,
  dedupeRisks,
  computeStats,
  countUnmapped,
  buildRiskEdges,
} from "./analysisMapping";

describe("extractRiskList", () => {
  it("prefers `results` (from /upload)", () => {
    expect(extractRiskList({ results: [1], risks: [2] })).toEqual([1]);
  });
  it("falls back to `risks` (from /analysis/{id}) — the Bug 1 fix", () => {
    expect(extractRiskList({ risks: [{ risk_id: "r1" }] })).toEqual([{ risk_id: "r1" }]);
  });
  it("returns [] for empty/missing payloads", () => {
    expect(extractRiskList({})).toEqual([]);
    expect(extractRiskList(null)).toEqual([]);
  });
});

describe("buildRisksMap", () => {
  it("keys a risk under both clause sections", () => {
    const risk = { risk_id: "r1", clause_a_section: "MSA-1", clause_b_section: "SOW-2" };
    const map = buildRisksMap([risk]);
    expect(map["MSA-1"]).toBe(risk);
    expect(map["SOW-2"]).toBe(risk);
  });
  it("skips null sections (partial mapping, Bug 2)", () => {
    const risk = { risk_id: "r1", clause_a_section: "MSA-1", clause_b_section: null };
    const map = buildRisksMap([risk]);
    expect(Object.keys(map)).toEqual(["MSA-1"]);
  });
  it("first writer wins for a shared section", () => {
    const a = { risk_id: "a", clause_b_section: "MSA-1" };
    const b = { risk_id: "b", clause_b_section: "MSA-1" };
    expect(buildRisksMap([a, b])["MSA-1"]).toBe(a);
  });
});

describe("mapNodesWithRisk", () => {
  it("keeps an explicit backend has_risk=true flag", () => {
    const nodes = [{ id: "MSA-1", has_risk: true }, { id: "MSA-2", has_risk: false }];
    const out = mapNodesWithRisk(nodes, {});
    expect(out[0].has_risk).toBe(true);
    expect(out[1].has_risk).toBe(false);
  });
  it("derives has_risk from the map when the flag is absent", () => {
    const nodes = [{ id: "MSA-1" }, { id: "MSA-2" }];
    const out = mapNodesWithRisk(nodes, { "MSA-1": {} });
    expect(out[0].has_risk).toBe(true);
    expect(out[1].has_risk).toBe(false);
  });
  it("derives has_risk even when the backend sent has_risk=false (the real-data bug)", () => {
    // The graph is built before risk detection, so every node arrives with
    // has_risk===false. A risk mapping to the node must still light it up.
    const nodes = [{ id: "MSA-2.3.2", has_risk: false }, { id: "MSA-1", has_risk: false }];
    const out = mapNodesWithRisk(nodes, { "MSA-2.3.2": { risk_id: "r1" } });
    expect(out[0].has_risk).toBe(true);
    expect(out[1].has_risk).toBe(false);
  });
});

describe("dedupeRisks", () => {
  it("dedupes by object reference, not risk_id", () => {
    // Same risk keyed under two sections must appear once.
    const risk = { risk_id: "r1", clause_a_section: "MSA-1", clause_b_section: "SOW-2" };
    const map = buildRisksMap([risk]);
    expect(dedupeRisks(map)).toEqual([risk]);
  });
  it("keeps distinct risks that happen to share a risk_id", () => {
    // Real data has non-unique risk_ids; distinct objects must both survive.
    const a = { risk_id: "dup", clause_b_section: "MSA-1" };
    const b = { risk_id: "dup", clause_b_section: "MSA-2" };
    expect(dedupeRisks(buildRisksMap([a, b]))).toHaveLength(2);
  });
});

describe("buildRiskEdges", () => {
  it("creates a conflict edge tagged with the conflict type", () => {
    const risks = [{ type: "CONTRADICTION", clause_a_section: "MSA-4.2", clause_b_section: "SOW-2.2" }];
    const edges = buildRiskEdges(risks);
    expect(edges).toEqual([
      { from: "MSA-4.2", to: "SOW-2.2", edge_type: "contradiction", conflict_type: "CONTRADICTION", is_risk_edge: true },
    ]);
  });
  it("maps risk type to edge_type (override / circular)", () => {
    const risks = [
      { type: "OVERRIDE", clause_a_section: "MSA-5", clause_b_section: "SOW-6" },
      { type: "CIRCULAR_REFERENCE", clause_a_section: "SOW-5", clause_b_section: "SOW-9" },
    ];
    expect(buildRiskEdges(risks).map((e) => e.edge_type)).toEqual(["override", "circular"]);
  });
  it("skips risks without two distinct clause sections (e.g. missing-doc)", () => {
    const risks = [
      { type: "MISSING_DOCUMENT", clause_a_section: "MSA-2.3.2", clause_b_section: null },
      { type: "CONTRADICTION", clause_a_section: "MSA-1", clause_b_section: "MSA-1" },
    ];
    expect(buildRiskEdges(risks)).toEqual([]);
  });
  it("dedupes identical from/to/type edges", () => {
    const risks = [
      { type: "CONTRADICTION", clause_a_section: "MSA-4.2", clause_b_section: "SOW-2.2" },
      { type: "CONTRADICTION", clause_a_section: "MSA-4.2", clause_b_section: "SOW-2.2" },
    ];
    expect(buildRiskEdges(risks)).toHaveLength(1);
  });
});

describe("computeStats", () => {
  it("counts docs and critical/blocker findings", () => {
    const nodes = [
      { id: "MSA-1", document_type: "MSA" },
      { id: "SOW-1", document_type: "SOW" },
      { id: "SOW-2", document_type: "SOW" },
    ];
    const allRisks = [
      { severity: "CRITICAL" },
      { severity: "BLOCKER" },
      { severity: "LOW" },
    ];
    expect(computeStats(nodes, allRisks)).toEqual({
      msaCount: 1,
      sowCount: 2,
      riskCount: 3,
      criticalCount: 2,
    });
  });
});

describe("countUnmapped", () => {
  it("counts findings with no matching graph node or a null section", () => {
    const nodes = [{ id: "MSA-1" }];
    const allRisks = [
      { clause_b_section: "MSA-1" },            // mapped
      { clause_b_section: "SOW-9" },            // no node
      { clause_a_section: null, clause_b_section: null }, // null section
    ];
    expect(countUnmapped(nodes, allRisks)).toBe(2);
  });
});

describe("end-to-end mapping (the Bug 1 regression)", () => {
  it("populates risks from an /analysis payload shaped like the real API", () => {
    const payload = {
      graph: {
        nodes: [{ id: "MSA-1", document_type: "MSA" }, { id: "SOW-1", document_type: "SOW" }],
      },
      risks: [
        { risk_id: "r1", severity: "CRITICAL", clause_a_section: "MSA-1", clause_b_section: "SOW-1" },
        { risk_id: "r2", severity: "HIGH", clause_a_section: null, clause_b_section: "SOW-1" },
      ],
    };
    const map = buildRisksMap(extractRiskList(payload));
    const all = dedupeRisks(map);
    // r1 keyed under MSA-1 & SOW-1, r2 under SOW-1 (loses to r1) → SOW-1 already taken,
    // so r2 is only reachable if it has another key. Here it doesn't, so it's dropped
    // from the section map — this documents the known partial-mapping behaviour.
    expect(all.length).toBeGreaterThanOrEqual(1);
    expect(map["MSA-1"].risk_id).toBe("r1");
    const nodes = mapNodesWithRisk(payload.graph.nodes, map);
    expect(nodes.find((n) => n.id === "MSA-1").has_risk).toBe(true);
    expect(nodes.find((n) => n.id === "SOW-1").has_risk).toBe(true);
  });
});
