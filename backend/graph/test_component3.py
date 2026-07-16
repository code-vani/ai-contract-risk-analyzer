"""
Component 3 test — run from the backend/ directory:
    cd backend
    python graph/test_component3.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai.clause_extractor import extract_clauses
from graph.graph_builder import build_graph
from graph.cycle_detector import find_cycles, is_dag
from graph.edge_analyzer import (
    tag_cross_document_edges, find_topic_pairs,
    find_hub_clauses, find_override_chains, get_topological_order,
)
from graph.graph_serializer import graph_to_json
import glob
from config import CUAD_DIR


# ── Load real clauses from CUAD (uses Component 2 cache — instant) ───────────

def load_cuad_clauses(doc_type: str, idx: int = 0) -> list:
    txts = glob.glob(os.path.join(CUAD_DIR, "CUAD_v1", "full_contract_txt", "**", "*.txt"), recursive=True)
    if not txts:
        return []
    path = txts[idx]
    print(f"  Loading {doc_type}: {os.path.basename(path)}")
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    result = {"mode": "text", "content": text, "file_type": "txt"}
    return extract_clauses(result, doc_type, file_path=path)


# ── Inject artificial cycles & overrides for demo purposes ───────────────────

def inject_demo_clauses(base_clauses: list) -> list:
    """
    Add a few synthetic clauses so tests are deterministic
    and show the interesting features (cycles, overrides, hub).
    Real contracts rarely have cycles — we need to force one for testing.
    """
    demo = base_clauses.copy()
    demo += [
        {
            "section_number": "99.1", "title": "Demo Cycle Start",
            "text": "This clause is governed by Section 99.2.",
            "document_type": "MSA", "clause_type": "other",
            "has_obligation": True, "references_to": ["99.2"],
        },
        {
            "section_number": "99.2", "title": "Demo Cycle End",
            "text": "Notwithstanding Section 99.1 this clause refers back to Section 99.1.",
            "document_type": "MSA", "clause_type": "other",
            "has_obligation": True, "references_to": ["99.1"],
        },
        {
            "section_number": "2.2", "title": "SOW Payment — 45 days",
            "text": "Notwithstanding Section 2.2 of the MSA, invoices shall be paid within 45 days.",
            "document_type": "SOW", "clause_type": "payment",
            "has_obligation": True, "references_to": ["2.2"],
        },
        {
            "section_number": "3.1", "title": "SOW Termination",
            "text": "Either party may terminate this SOW per Section 3.1 of the MSA.",
            "document_type": "SOW", "clause_type": "termination",
            "has_obligation": True, "references_to": ["3.1"],
        },
    ]
    return demo


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_graph_build(clauses):
    print("\n[Test 1] Graph build")
    graph = build_graph(clauses)
    print(f"  Nodes: {graph.number_of_nodes()}")
    print(f"  Edges: {graph.number_of_edges()}")
    assert graph.number_of_nodes() > 0, "Graph should have nodes"
    print("  [PASS]")
    return graph


def test_cycle_detection(graph):
    print("\n[Test 2] Cycle detection")
    cycles = find_cycles(graph)
    dag    = is_dag(graph)
    print(f"  Cycles found: {len(cycles)}")
    print(f"  Is DAG: {dag}")
    for c in cycles:
        print(f"  Loop: {' -> '.join(c['cycle_path'])}")
    assert len(cycles) >= 1, "Should find the injected cycle (99.1 <-> 99.2)"
    assert not dag, "Graph with cycles is not a DAG"
    print("  [PASS]")
    return cycles


def test_edge_analysis(graph, clauses):
    print("\n[Test 3] Edge analysis")
    cross_pairs = tag_cross_document_edges(graph)
    topic_pairs = find_topic_pairs(clauses)
    hubs        = find_hub_clauses(graph, top_n=3)
    chains      = find_override_chains(graph, clauses)
    topo        = get_topological_order(graph)

    print(f"  Cross-document pairs: {len(cross_pairs)}")
    print(f"  Topic pairs (for contradiction check): {len(topic_pairs)}")
    print(f"  Hub clauses (top 3):")
    for h in hubs:
        print(f"    {h['node_id']} — referenced by {h['referenced_by']} clause(s) [{h['severity']}]")
    print(f"  Override chains (2+ hops): {len(chains)}")
    print(f"  Topological order available: {topo is not None}")

    assert len(topic_pairs) >= 1, "Should find at least one topic pair"
    print("  [PASS]")
    return cross_pairs, topic_pairs, hubs, chains


def test_serialization(graph, cycles, hubs):
    print("\n[Test 4] Graph serialization")
    graph_json = graph_to_json(graph, cycles)

    nodes = graph_json["nodes"]
    edges = graph_json["edges"]
    stats = graph_json["stats"]

    print(f"  Nodes serialized: {len(nodes)}")
    print(f"  Edges serialized: {len(edges)}")
    print(f"  Is DAG: {graph_json['is_dag']}")
    print(f"  Hub clauses: {len(graph_json['hub_clauses'])}")
    print(f"  Stats: {json.dumps(stats, indent=4)}")

    # Verify node structure matches what Vis.js expects
    node = nodes[0]
    for field in ("id", "label", "color", "shape", "document_type", "clause_type"):
        assert field in node, f"Node missing field: {field}"

    # Check cycle nodes are marked
    cycle_nodes = [n for n in nodes if n.get("in_cycle")]
    print(f"  Cycle-flagged nodes: {len(cycle_nodes)}")
    assert len(cycle_nodes) >= 2, "Should flag the injected cycle nodes"

    # Check hub nodes are marked
    hub_nodes = [n for n in nodes if n.get("is_hub")]
    print(f"  Hub-flagged nodes: {len(hub_nodes)}")

    print("  [PASS]")
    return graph_json


if __name__ == "__main__":
    print("=" * 60)
    print("Component 3 — Dependency Graph Tests")
    print("=" * 60)

    print("\nLoading CUAD clauses (cache hit expected)...")
    msa_clauses = load_cuad_clauses("MSA", idx=0)
    sow_clauses = load_cuad_clauses("SOW", idx=1)
    print(f"  MSA clauses: {len(msa_clauses)}, SOW clauses: {len(sow_clauses)}")

    all_clauses = inject_demo_clauses(msa_clauses + sow_clauses)
    print(f"  Total with demo injections: {len(all_clauses)}")

    graph      = test_graph_build(all_clauses)
    cycles     = test_cycle_detection(graph)
    cross, topics, hubs, chains = test_edge_analysis(graph, all_clauses)
    graph_json = test_serialization(graph, cycles, hubs)

    print("\n" + "=" * 60)
    print("All Component 3 tests passed!")
    print("=" * 60)
    print(f"\nSummary of what Component 3 produces:")
    print(f"  {graph_json['stats']['total_nodes']} nodes, {graph_json['stats']['total_edges']} edges")
    print(f"  {graph_json['stats']['cycle_count']} circular reference(s)")
    print(f"  {graph_json['stats']['cross_document_edges']} cross-document edge(s)")
    print(f"  {graph_json['stats']['hub_count']} hub clause(s)")
    print(f"  Is clean DAG: {graph_json['is_dag']}")
    print(f"\n  Topic pairs ready for Component 4: {len(topics)}")
    print(f"  Cross-doc pairs ready for Component 4: {len(cross)}")
