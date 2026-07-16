import React from "react";
import { AlertOctagon, RotateCcw } from "lucide-react";

/**
 * Catches render/runtime errors anywhere below it so a single throw doesn't
 * blank the whole app to a white screen.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Surface to the console for debugging; a real deployment could ship this
    // to an error tracker here.
    console.error("Uncaught UI error:", error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="min-h-screen app-shell flex items-center justify-center p-6 text-slate-100 font-sans">
        <div className="glass-card p-10 max-w-lg text-center flex flex-col items-center gap-4">
          <div className="p-4 rounded-2xl" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}>
            <AlertOctagon className="w-8 h-8 text-rose-400" />
          </div>
          <h1 className="text-lg font-bold text-white font-['Outfit']">Something went wrong</h1>
          <p className="text-[12px] text-slate-500 leading-relaxed">
            The interface hit an unexpected error and stopped rendering this view. Your data is safe on the server — reloading usually fixes it.
          </p>
          <pre className="text-[10px] text-rose-300/70 bg-rose-500/5 border border-rose-500/15 rounded-lg p-2.5 max-w-full overflow-x-auto text-left">
            {String(this.state.error?.message || this.state.error)}
          </pre>
          <button onClick={() => window.location.reload()} className="btn-primary-cta px-4 py-2 text-[12px] flex items-center gap-1.5">
            <RotateCcw className="w-3.5 h-3.5" /> Reload App
          </button>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
