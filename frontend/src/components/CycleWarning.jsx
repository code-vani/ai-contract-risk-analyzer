import React from "react";
import { AlertOctagon, Repeat } from "lucide-react";

const CycleWarning = ({ circularReferences = [], onSelectNode = () => {} }) => {
  if (circularReferences.length === 0) return null;

  return (
    <div className="glass-card p-4 space-y-3 animate-fade-up pulse-error" style={{ animationDelay: '0.15s', borderColor: 'rgba(239,68,68,0.15)' }}>
      <div className="flex items-center gap-2 text-red-400 font-bold text-[11px] uppercase tracking-wider font-['Outfit']">
        <AlertOctagon className="w-4 h-4 animate-pulse shrink-0" />
        <span>{circularReferences.length} Circular Loop{circularReferences.length > 1 ? 's' : ''} Detected</span>
      </div>
      <p className="text-[10px] text-slate-500 leading-relaxed">
        Clauses reference each other recursively, creating unresolvable legal dependencies. Click to locate:
      </p>

      <div className="space-y-2">
        {circularReferences.map((cycle, idx) => (
          <div
            key={idx}
            className="p-3 rounded-xl flex items-start gap-2.5 text-xs text-slate-300"
            style={{ background: 'rgba(6,9,17,0.6)', border: '1px solid rgba(239,68,68,0.1)' }}
          >
            <Repeat className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
            <div className="space-y-2 min-w-0">
              <span className="font-mono text-red-400 font-bold text-[10px] block uppercase tracking-wider">
                Loop #{idx + 1}
              </span>

              <div className="flex flex-wrap items-center gap-1">
                {cycle.cycle_path.map((nodeId, nodeIdx) => (
                  <React.Fragment key={nodeIdx}>
                    {nodeIdx > 0 && <span className="text-slate-600 font-bold mx-0.5 text-[10px]">→</span>}
                    <button
                      onClick={() => onSelectNode(nodeId)}
                      className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold transition-all cursor-pointer"
                      style={{
                        background: 'rgba(239,68,68,0.08)',
                        border: '1px solid rgba(239,68,68,0.2)',
                        color: '#fca5a5',
                      }}
                      onMouseEnter={(e) => {
                        e.target.style.background = 'rgba(239,68,68,0.2)';
                        e.target.style.borderColor = 'rgba(239,68,68,0.4)';
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.background = 'rgba(239,68,68,0.08)';
                        e.target.style.borderColor = 'rgba(239,68,68,0.2)';
                      }}
                      title={`Focus on ${nodeId.replace("-", " Section ")}`}
                    >
                      {nodeId.replace("-", " § ")}
                    </button>
                  </React.Fragment>
                ))}
              </div>

              <p className="text-slate-500 text-[10px] leading-relaxed">
                {cycle.description || "The clauses above create a mutual dependency, locking execution."}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CycleWarning;
