import networkx as nx
from graph.cycle_detector import is_dag
from graph.edge_analyzer import find_hub_clauses

# Vis.js node colors by document type and status
_COLORS = {
    "MSA":         {"background": "#7F77DD", "border": "#5a52b8", "font": {"color": "#fff"}},
    "SOW":         {"background": "#1D9E75", "border": "#14785a", "font": {"color": "#fff"}},
    "risk":        {"background": "#E24B4A", "border": "#b33332", "font": {"color": "#fff"}},
    "cycle":       {"background": "#8B0000", "border": "#600000", "font": {"color": "#fff"}},
    "hub":         {"background": "#F59E0B", "border": "#b45309", "font": {"color": "#fff"}},
    "financial":   {"background": "#6B7280", "border": "#374151", "font": {"color": "#fff"}},
}

_EDGE_STYLES = {
    "reference":      {"color": "#9CA3AF", "dashes": False, "width": 1},
    "cross_document": {"color": "#3B82F6", "dashes": False, "width": 2},
    "override":       {"color": "#EF4444", "dashes": [6, 3], "width": 2},
}


def graph_to_json(
    graph: nx.DiGraph,
    cycles: list,
    risks: list = None,
    hub_top_n: int = 5,
) -> dict:
    """
    Convert a NetworkX graph to JSON ready for Vis.js rendering.

    Each node gets colour-coded:
      Purple   → MSA clause (normal)
      Teal     → SOW clause (normal)
      Red      → clause involved in a detected risk
      Dark red → clause in a circular reference cycle
      Amber    → hub clause (referenced by many others)
      Grey     → financial table clause

    Returns:
      {
        nodes: [...],          ← Vis.js node objects
        edges: [...],          ← Vis.js edge objects
        circular_references,   ← cycle list from cycle_detector
        hub_clauses,           ← high-impact nodes
        is_dag,                ← boolean — graph has no cycles
        stats: { ... }         ← summary counts
      }
    """
    # Build sets for fast O(1) lookups during serialization
    cycle_node_ids = {n for c in cycles for n in c.get("node_ids", [])}

    risk_node_ids = set()
    if risks:
        for r in risks:
            risk_node_ids.add(f"{r.get('clause_a_section', '')}")
            risk_node_ids.add(f"{r.get('clause_b_section', '')}")

    hubs = find_hub_clauses(graph, top_n=hub_top_n)
    hub_node_ids = {h["node_id"] for h in hubs}

    # Serialize nodes
    nodes = []
    for node_id, attrs in graph.nodes(data=True):
        doc_type   = attrs.get("document_type", "MSA")
        clause_type = attrs.get("clause_type", "other")

        # Determine colour priority: cycle > risk > hub > financial_table > doc type
        if node_id in cycle_node_ids:
            color = _COLORS["cycle"]
        elif node_id in risk_node_ids:
            color = _COLORS["risk"]
        elif node_id in hub_node_ids:
            color = _COLORS["hub"]
        elif clause_type == "financial_table":
            color = _COLORS["financial"]
        else:
            color = _COLORS.get(doc_type, _COLORS["MSA"])

        sec = attrs.get("section_number", "?")
        nodes.append({
            "id":             node_id,
            "label":          f"{doc_type}\n§ {sec}",
            "title":          attrs.get("title", ""),    # tooltip on hover
            "text":           attrs.get("text", ""),     # full text for side panel
            "document_type":  doc_type,
            "clause_type":    clause_type,
            "section_number": sec,
            "has_obligation": attrs.get("has_obligation", False),
            "in_cycle":       node_id in cycle_node_ids,
            "has_risk":       node_id in risk_node_ids,
            "is_hub":         node_id in hub_node_ids,
            "color":          color,
            "shape":          "box",
        })

    # Serialize edges
    edges = []
    for i, (src, tgt, data) in enumerate(graph.edges(data=True)):
        edge_type = data.get("edge_type", "reference")
        style     = _EDGE_STYLES.get(edge_type, _EDGE_STYLES["reference"])
        edges.append({
            "id":        i,
            "from":      src,
            "to":        tgt,
            "edge_type": edge_type,
            **style,
            "arrows":    "to",
        })

    return {
        "nodes":               nodes,
        "edges":               edges,
        "circular_references": cycles,
        "hub_clauses":         hubs,
        "is_dag":              is_dag(graph),
        "stats": {
            "total_nodes":          graph.number_of_nodes(),
            "total_edges":          graph.number_of_edges(),
            "cross_document_edges": sum(1 for _, _, d in graph.edges(data=True) if d.get("edge_type") == "cross_document"),
            "cycle_count":          len(cycles),
            "hub_count":            len(hubs),
            "msa_clauses":          sum(1 for _, d in graph.nodes(data=True) if d.get("document_type") == "MSA"),
            "sow_clauses":          sum(1 for _, d in graph.nodes(data=True) if d.get("document_type") == "SOW"),
        },
    }
