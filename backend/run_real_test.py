import os, sys, json
os.environ["USE_MOCKS"] = "false"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline

result = pipeline.run_analysis(
    "demo/TexasAM_MSA.pdf",
    "demo/TexasAM_SOW.pdf",
    "TexasAM_MSA.pdf",
    "TexasAM_SOW.pdf",
)

print("\n=== SUMMARY ===")
print(json.dumps(result["summary"], indent=2))

print("\n=== MISSING DOCS ===")
for m in result.get("missing_docs", []):
    print(f"  {m['severity']} | {m['referenced_document']} | clause: {m.get('clause_section','?')}")

print("\n=== RISKS ===")
for r in result.get("results", []):
    print(f"  {r['severity']} | {r['type']} | {r.get('description','')[:80]}")

print("\n=== GRAPH ===")
g = result["graph"]
print(f"  nodes:{len(g['nodes'])}, edges:{len(g['edges'])}, cycles:{len(g.get('circular_references', []))}")
