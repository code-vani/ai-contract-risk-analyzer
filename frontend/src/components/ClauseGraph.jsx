import React, { useEffect, useRef, forwardRef, useImperativeHandle } from "react";
import { Network } from "vis-network";
import { DataSet } from "vis-data";
import "vis-network/styles/vis-network.css";
import { Crosshair, ZoomIn, ZoomOut } from "lucide-react";

// vis-network renders a STRING title as literal text (so HTML would leak on
// screen). Build a real DOM element instead — it renders as HTML and safely
// escapes the clause text via textContent.
const buildTooltip = (node) => {
  const el = document.createElement("div");
  el.style.cssText = "font-family:Inter,system-ui;font-size:12px;max-width:260px;padding:10px 12px;line-height:1.6;color:#94a3b8;background:#0F172A;border:1px solid #1E293B;border-radius:8px;";
  const strong = document.createElement("strong");
  strong.style.cssText = "color:#e2e8f0;display:block;margin-bottom:4px;font-size:13px;";
  strong.textContent = `${node.document_type} § ${node.section_number || node.id} — ${node.title || ""}`;
  el.appendChild(strong);
  if (node.text) {
    const span = document.createElement("span");
    span.textContent = node.text.substring(0, 180) + (node.text.length > 180 ? "…" : "");
    el.appendChild(span);
  }
  return el;
};

// Document-type palette — MSA reads blue, SOW reads green, everywhere.
const MSA_FILL = "#6366f1", MSA_BORDER = "#4f46e5", MSA_HI = "#818cf8", MSA_GLOW = "rgba(99, 102, 241, 0.28)";
const SOW_FILL = "#0d9488", SOW_BORDER = "#0f766e", SOW_HI = "#14b8a6", SOW_GLOW = "rgba(13, 148, 136, 0.28)";
const RISK_RING = "#f43f5e", RISK_RING_HI = "#fb7185", RISK_GLOW = "rgba(244, 63, 94, 0.45)";

// Truncate a clause title so it fits inside a circle node.
const shortTitle = (t) => {
  if (!t) return "";
  return t.length > 14 ? t.slice(0, 13) + "…" : t;
};

// Derive the document a node id belongs to (ids look like "MSA-4.2" / "SOW-1").
const docOf = (id) => (typeof id === "string" && id.toUpperCase().startsWith("SOW") ? "SOW" : "MSA");

// ── Pure builders (no vis instance) so they're easy to reason about/test ──────
const buildVisNode = (node, { selectedNodeId, circularReferences }) => {
  const isSelected = node.id === selectedNodeId;
  const isInCycle = circularReferences.some((cycle) => cycle.cycle_path.includes(node.id));
  const isMsa = node.document_type === "MSA";
  const risky = node.has_risk || isInCycle;

  const background = isMsa ? MSA_FILL : SOW_FILL;
  const highlightBg = isMsa ? MSA_HI : SOW_HI;
  const border = risky ? RISK_RING : isMsa ? MSA_BORDER : SOW_BORDER;
  const highlightBorder = risky ? RISK_RING_HI : isMsa ? MSA_FILL : SOW_FILL;

  const section = node.section_number || node.id.replace(/^[^-]+-/, "");
  // Two-line label: "§4.1" on line 1, short title on line 2
  // Plain text mode (\n creates real line breaks when multi is not set)
  const label = `§${section}\n${shortTitle(node.title)}`;

  return {
    id: node.id,
    label,
    title: buildTooltip(node),
    shape: "circle",
    margin: 10,
    borderWidth: isSelected ? 5 : risky ? 4 : 2,
    borderWidthSelected: 5,
    color: { background, border, highlight: { background: highlightBg, border: highlightBorder } },
    font: {
      color: "#ffffff",
      size: 13,
      face: "Inter, system-ui, sans-serif",
      // Do NOT set multi — plain text mode is the default and correctly
      // treats \n as a line break. HTML mode ignores \n.
    },
    shadow: {
      enabled: true,
      color: risky ? RISK_GLOW : isMsa ? MSA_GLOW : SOW_GLOW,
      size: isSelected ? 22 : risky ? 16 : 12,
      x: 0,
      y: 4,
    },
    chosen: {
      node: (values) => {
        values.borderWidth = 5;
        values.shadow = true;
        values.shadowSize = 24;
      },
    },
  };
};

// Human labels for the conflict types shown on the connecting line.
const CONFLICT_LABEL = {
  CONTRADICTION: "CONTRADICTION",
  OVERRIDE: "OVERRIDE",
  CIRCULAR_REFERENCE: "CIRCULAR",
};

const buildVisEdge = (edge) => {
  const conflictType = edge.conflict_type
    || (edge.edge_type === "contradiction" ? "CONTRADICTION"
      : edge.edge_type === "override" ? "OVERRIDE"
      : edge.edge_type === "circular" ? "CIRCULAR_REFERENCE"
      : null);

  let color, width, dashes, label;

  if (conflictType === "CONTRADICTION") {
    color = "#f43f5e"; width = 3; dashes = [8, 5]; label = CONFLICT_LABEL.CONTRADICTION;
  } else if (conflictType === "OVERRIDE") {
    color = "#f59e0b"; width = 3; dashes = [6, 4]; label = CONFLICT_LABEL.OVERRIDE;
  } else if (conflictType === "CIRCULAR_REFERENCE") {
    color = "#991b1b"; width = 3; dashes = [2, 4]; label = CONFLICT_LABEL.CIRCULAR_REFERENCE;
  } else if (edge.edge_type === "cross_document" || docOf(edge.from) !== docOf(edge.to)) {
    color = "#64748b"; width = 1.5; dashes = [4, 4]; label = "";
  } else if (docOf(edge.from) === "MSA") {
    color = MSA_FILL; width = 2; dashes = false; label = "";
  } else {
    color = SOW_FILL; width = 2; dashes = false; label = "";
  }

  return {
    id: `${edge.from}-${edge.to}-${conflictType || edge.edge_type || "ref"}`,
    from: edge.from,
    to: edge.to,
    label,
    arrows: { to: { enabled: true, scaleFactor: 0.7, type: "arrow" } },
    color: { color, highlight: color, hover: color, opacity: conflictType ? 1 : 0.85 },
    width,
    dashes,
    font: {
      color, size: conflictType ? 9 : 8, face: "JetBrains Mono, monospace", strokeWidth: 0,
      align: "middle", background: "rgba(6, 9, 17, 0.9)",
    },
    smooth: { enabled: true, type: "cubicBezier", forceDirection: "horizontal", roundness: 0.4 },
    hoverWidth: 1.5,
  };
};

const ClauseGraph = forwardRef(({
  nodes = [],
  edges = [],
  circularReferences = [],
  selectedNodeId = null,
  onNodeClick = () => {},
  filters = { showMsa: true, showSow: true, showRisksOnly: false },
}, ref) => {
  const containerRef = useRef(null);
  const networkRef = useRef(null);
  const nodesDsRef = useRef(null);
  const edgesDsRef = useRef(null);
  const layoutSigRef = useRef("");
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;

  // Expose fit/zoom controls to parent via ref
  useImperativeHandle(ref, () => ({
    fit: () => networkRef.current?.fit({ animation: { duration: 600, easingFunction: "easeInOutQuad" } }),
    zoomIn: () => {
      const scale = networkRef.current?.getScale() || 1;
      networkRef.current?.moveTo({ scale: scale * 1.3, animation: { duration: 300, easingFunction: "easeInOutQuad" } });
    },
    zoomOut: () => {
      const scale = networkRef.current?.getScale() || 1;
      networkRef.current?.moveTo({ scale: scale * 0.7, animation: { duration: 300, easingFunction: "easeInOutQuad" } });
    },
  }), []);

  // ── Create the network exactly once ────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const nodesDs = new DataSet([]);
    const edgesDs = new DataSet([]);
    nodesDsRef.current = nodesDs;
    edgesDsRef.current = edgesDs;

    const network = new Network(
      containerRef.current,
      { nodes: nodesDs, edges: edgesDs },
      {
        physics: {
          enabled: true,
          solver: "barnesHut",
          barnesHut: {
            gravitationalConstant: -3000,
            centralGravity: 0.25,
            springLength: 180,
            springConstant: 0.035,
            damping: 0.12,
            avoidOverlap: 0.8,
          },
          stabilization: { enabled: true, iterations: 200, updateInterval: 25 },
          maxVelocity: 30,
          minVelocity: 0.75,
        },
        interaction: {
          hover: true,
          dragNodes: true,
          dragView: true,
          zoomView: true,
          selectable: true,
          tooltipDelay: 150,
          navigationButtons: false,
          keyboard: false,
        },
        layout: { randomSeed: 42 },
      }
    );
    networkRef.current = network;

    network.on("click", (params) => {
      onNodeClickRef.current(params.nodes.length > 0 ? params.nodes[0] : null);
    });

    network.on("stabilizationIterationsDone", () => {
      network.setOptions({ physics: { enabled: false } });
    });

    return () => {
      network.destroy();
      networkRef.current = null;
      nodesDsRef.current = null;
      edgesDsRef.current = null;
    };
  }, []);

  // ── Sync data in place whenever inputs change ───────────────────────────────
  useEffect(() => {
    const nodesDs = nodesDsRef.current;
    const edgesDs = edgesDsRef.current;
    if (!nodesDs || !edgesDs) return;

    const visNodes = nodes
      .filter((node) => {
        if (node.document_type === "MSA" && !filters.showMsa) return false;
        if (node.document_type === "SOW" && !filters.showSow) return false;
        if (filters.showRisksOnly && !node.has_risk) return false;
        return true;
      })
      .map((node) => buildVisNode(node, { selectedNodeId, circularReferences }));

    const activeNodeIds = new Set(visNodes.map((n) => n.id));
    const visEdges = edges
      .filter((edge) => activeNodeIds.has(edge.from) && activeNodeIds.has(edge.to))
      .map(buildVisEdge);

    const nextNodeIds = new Set(visNodes.map((n) => n.id));
    const staleNodeIds = nodesDs.getIds().filter((id) => !nextNodeIds.has(id));
    if (staleNodeIds.length) nodesDs.remove(staleNodeIds);
    nodesDs.update(visNodes);

    const nextEdgeIds = new Set(visEdges.map((e) => e.id));
    const staleEdgeIds = edgesDs.getIds().filter((id) => !nextEdgeIds.has(id));
    if (staleEdgeIds.length) edgesDs.remove(staleEdgeIds);
    edgesDs.update(visEdges);

    const sig = visNodes.map((n) => n.id).sort().join("|");
    if (sig !== layoutSigRef.current) {
      layoutSigRef.current = sig;
      const network = networkRef.current;
      if (network) {
        network.setOptions({ physics: { enabled: true } });
        network.stabilize(200);
      }
    }
  }, [nodes, edges, circularReferences, filters, selectedNodeId]);

  // ── React to selection changes without touching the data set ────────────────
  useEffect(() => {
    const network = networkRef.current;
    if (!network) return;
    if (selectedNodeId && nodesDsRef.current?.get(selectedNodeId)) {
      network.selectNodes([selectedNodeId]);
      network.focus(selectedNodeId, {
        scale: 1.2,
        animation: { duration: 600, easingFunction: "easeInOutQuad" },
      });
    } else {
      network.unselectAll();
    }
  }, [selectedNodeId]);

  const handleFit = () =>
    networkRef.current?.fit({ animation: { duration: 600, easingFunction: "easeInOutQuad" } });
  const handleZoomIn = () => {
    const s = networkRef.current?.getScale() || 1;
    networkRef.current?.moveTo({ scale: s * 1.3, animation: { duration: 300, easingFunction: "easeInOutQuad" } });
  };
  const handleZoomOut = () => {
    const s = networkRef.current?.getScale() || 1;
    networkRef.current?.moveTo({ scale: s * 0.7, animation: { duration: 300, easingFunction: "easeInOutQuad" } });
  };

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden">
      <div ref={containerRef} className="w-full h-full" style={{ minHeight: "550px" }} />

      {/* Floating controls — always visible, even in fullscreen */}
      <div style={{ position: "absolute", bottom: 16, left: 16, zIndex: 10, display: "flex", alignItems: "center", gap: 6 }}>
        <button onClick={handleFit} className="btn-glass" style={{ padding: "6px 12px", fontSize: 11, display: "flex", alignItems: "center", gap: 5 }} title="Fit all nodes">
          <Crosshair style={{ width: 13, height: 13 }} /> Fit
        </button>
        <button onClick={handleZoomIn} className="btn-glass" style={{ padding: "6px 10px" }} title="Zoom in">
          <ZoomIn style={{ width: 13, height: 13 }} />
        </button>
        <button onClick={handleZoomOut} className="btn-glass" style={{ padding: "6px 10px" }} title="Zoom out">
          <ZoomOut style={{ width: 13, height: 13 }} />
        </button>
      </div>
    </div>
  );
});

ClauseGraph.displayName = "ClauseGraph";

export default ClauseGraph;
