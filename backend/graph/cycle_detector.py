import networkx as nx


def find_cycles(graph: nx.DiGraph) -> list:
    """
    Find all circular references in the clause dependency graph.

    A cycle means: Clause A → Clause B → ... → Clause A
    This is a drafting error — the contract can never resolve which
    clause governs, creating an infinite loop of interpretation.

    Returns list of cycle dicts, each with:
      cycle_path   → the node IDs in the loop (last == first to close it)
      severity     → always CRITICAL
      description  → human-readable explanation
      length       → how many clauses are in the loop
    """
    cycles = []
    try:
        for cycle in nx.simple_cycles(graph):
            if len(cycle) < 2:
                continue
            closed_path = cycle + [cycle[0]]
            path_str    = " -> ".join(closed_path)
            cycles.append({
                "cycle_path":  closed_path,
                "node_ids":    cycle,
                "severity":    "CRITICAL",
                "length":      len(cycle),
                "description": (
                    f"Circular reference detected ({len(cycle)} clauses): "
                    f"{path_str}. "
                    f"These clauses reference each other in a loop — "
                    f"the contract can never resolve which one governs."
                ),
            })
    except Exception as e:
        print(f"[CycleDetector] Error: {e}")

    if cycles:
        print(f"[CycleDetector] Found {len(cycles)} cycle(s)")
    else:
        print("[CycleDetector] Graph is cycle-free (DAG verified)")

    return cycles


def is_dag(graph: nx.DiGraph) -> bool:
    """Return True if the graph has no cycles — it is a Directed Acyclic Graph."""
    return nx.is_directed_acyclic_graph(graph)
