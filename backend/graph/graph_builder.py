import networkx as nx


def build_graph(clauses: list) -> nx.DiGraph:
    """
    Build a directed graph from a list of clause dicts.

    Nodes  → one per clause, keyed as "{document_type}-{section_number}"
             e.g. "MSA-4.1", "SOW-2.3"
    Edges  → clause A references clause B → directed edge A → B

    Node attributes stored for serialization and analysis:
      section_number, title, text, document_type, clause_type,
      has_obligation, references_to
    """
    G = nx.DiGraph()

    # Pass 1: add all nodes
    for clause in clauses:
        node_id = _node_id(clause)
        G.add_node(
            node_id,
            section_number=clause.get("section_number", ""),
            title=clause.get("title", ""),
            text=clause.get("text", ""),
            document_type=clause.get("document_type", ""),
            clause_type=clause.get("clause_type", "other"),
            has_obligation=clause.get("has_obligation", False),
            references_to=clause.get("references_to", []),
        )

    # Build a lookup: section_number → node_id (for both MSA and SOW)
    section_lookup: dict[str, list[str]] = {}
    for node_id, attrs in G.nodes(data=True):
        sec = attrs["section_number"]
        section_lookup.setdefault(sec, []).append(node_id)

    # Pass 2: add directed edges from references
    for clause in clauses:
        src = _node_id(clause)
        for ref in clause.get("references_to", []):
            # Skip named doc refs like "Exhibit A" — they aren't graph nodes
            if not ref[0].isdigit():
                continue
            # Try to find the referenced node — prefer same document, else cross-doc
            targets = _resolve_reference(ref, clause["document_type"], section_lookup)
            for tgt in targets:
                if tgt != src and not G.has_edge(src, tgt):
                    G.add_edge(src, tgt, edge_type="reference")

    return G


def _node_id(clause: dict) -> str:
    return f"{clause.get('document_type', 'DOC')}-{clause.get('section_number', '?')}"


def _resolve_reference(ref: str, src_doc: str, lookup: dict) -> list:
    """
    Given a reference string like "4.1", find matching node IDs.
    Prefer same-document match. If not found, return cross-document match.
    """
    candidates = lookup.get(ref, [])
    if not candidates:
        return []

    same_doc = [c for c in candidates if c.startswith(src_doc + "-")]
    if same_doc:
        return same_doc

    # Cross-document reference — return all matches
    return candidates
